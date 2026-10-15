"""Gerador de movimento em malha fechada: pegar um objeto e pôr no destino.

A cada passo de controle o gerador LÊ a posição atual do objeto (no robô real seria a
percepção) e recalcula o alvo; a cinemática inversa diferencial transforma o alvo da
ponta da garra em ângulos das 5 juntas do braço. Fases: aproximar, descer, fechar, subir,
levar, baixar, abrir, recuar. Cada fase vira um rótulo da anotação hierárquica.

SO-101: 5 juntas no braço. Com a garra para baixo, as 4 primeiras dão a posição e a inclinação,
e o giro do pulso (`wrist_roll`) escolhe para que lado a garra fecha. A garra não é simétrica:
um dedo fica parado e o outro gira; o objeto é pego encostado no dedo fixo.
Medido no modelo: garra reto para baixo alcança 15–30 cm da base até ~8 cm de altura; acima
disso a cinemática inversa inclina a garra sozinha (o erro de orientação pesa menos que o de posição).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import mujoco
import numpy as np

from .robos import SO101, Robo

PESO_ORIENTACAO = 0.05  # posição manda: 1 rad de inclinação pesa como 5 cm; inclina quando não alcança
PESO_GIRO = 0.5  # giro em torno do eixo da garra


@dataclass
class Fase:
    nome: str
    rotulo: str        # texto da primitiva (nível 3 da anotação)
    subtarefa: str     # nível 2
    max_s: float
    inicio: float = 0.0
    fim: float = 0.0


@dataclass
class Resultado:
    sucesso: bool
    motivo: str
    fases: list[Fase] = field(default_factory=list)
    eventos: list[dict] = field(default_factory=list)
    duracao: float = 0.0


def rot_garra(fecha: np.ndarray, aproxima: np.ndarray = np.array([0.0, 0.0, -1.0])) -> np.ndarray:
    """Matriz da ponta: colunas = (aproximação, y, direção em que a garra abre)."""
    a = aproxima / np.linalg.norm(aproxima)
    c = fecha - np.dot(fecha, a) * a
    c /= np.linalg.norm(c)
    return np.column_stack([a, np.cross(c, a), c])


def _ang(a: float) -> float:
    return (a + np.pi) % (2 * np.pi) - np.pi


class Gerador:
    def __init__(self, modelo: mujoco.MjModel, dados: mujoco.MjData, pegar: str, destino: str,
                 rng: np.random.Generator | None = None, vaga: tuple[float, float] = (0.0, 0.0),
                 deitar: bool = False, robo: Robo = SO101):
        self.m, self.d, self.robo = modelo, dados, robo
        self.pegar, self.destino = pegar, destino
        self.rng = rng or np.random.default_rng()
        self.tcp = modelo.site(robo.ponta).id
        self.obj = modelo.body(pegar).id
        self.alvo_site = modelo.site(destino + "_alvo").id if _tem_site(modelo, destino + "_alvo") else None
        self.alvo_corpo = modelo.body(destino).id
        self.vaga = np.array([vaga[0], vaga[1], 0.0])  # deslocamento dentro do recipiente
        self.juntas = [modelo.joint(n).id for n in robo.juntas]
        self.qadr = np.array([modelo.jnt_qposadr[j] for j in self.juntas])
        self.dadr = np.array([modelo.jnt_dofadr[j] for j in self.juntas])
        self.atu = [modelo.actuator(n).id for n in robo.juntas]
        self.atu_garra = modelo.actuator(robo.junta_garra).id
        self.qadr_garra = int(modelo.jnt_qposadr[modelo.joint(robo.junta_garra).id])
        self.n = robo.n
        self.aberta, self.fechada = robo.garra_aberta, robo.garra_fechada
        geom = modelo.geom(pegar + "_geom")
        self.meia_altura = float(modelo.geom_aabb[geom.id][5])  # meia altura (vale para malha também)
        self.dedos = set(_geoms_dos_dedos(modelo, robo))
        self.geom_obj = geom.id
        self.q_cmd = dados.qpos[self.qadr].copy()
        self.dk = mujoco.MjData(modelo)  # cópia só para a cinemática da postura comandada
        self.topo_acima = 0.03  # quanto do objeto fica acima do ponto da garra
        self.folga_deitar = 0.015
        self.inclinar = float(os.environ.get("R2S_INCLINAR", 60.0))
        self.deitar = deitar
        self.raio = float(modelo.geom_aabb[geom.id][3])
        self.esfera = modelo.geom_type[geom.id] == mujoco.mjtGeom.mjGEOM_SPHERE
        self.meia_altura_eixo = self.meia_altura
        mujoco.mj_forward(modelo, dados)
        self.fecha, self.largura = self._escolher_pegada()
        self.R_alvo = rot_garra(self.fecha)
        self.ultimo_erro = 0.0

    # ---------- percepção (no real: câmera + estimador de pose) ----------
    def pos_objeto(self) -> np.ndarray:
        return self.d.xpos[self.obj].copy()

    def pos_destino(self) -> np.ndarray:
        R = self.d.xmat[self.alvo_corpo].reshape(3, 3)
        if self.alvo_site is not None:
            return self.d.site_xpos[self.alvo_site].copy() + R @ self.vaga
        return self.d.xpos[self.alvo_corpo].copy() + R @ self.vaga

    def tocando(self) -> int:
        n = 0
        for i in range(self.d.ncon):
            c = self.d.contact[i]
            par = {c.geom1, c.geom2}
            if self.geom_obj in par and par & self.dedos:
                n += 1
        return n

    def dedos_tocando(self) -> set[int]:
        """Quais corpos de dedo (fixo, móvel) encostam no objeto."""
        corpos = set()
        for i in range(self.d.ncon):
            c = self.d.contact[i]
            par = {c.geom1, c.geom2}
            if self.geom_obj in par:
                for g in par & self.dedos:
                    corpos.add(int(self.m.geom_bodyid[g]))
        return corpos

    # ---------- pegada ----------
    def _escolher_pegada(self) -> tuple[np.ndarray, float]:
        """Direção em que a garra abre (horizontal) e a largura do objeto nessa direção.
        Sem giro do pulso a garra abre na direção radial (para longe da base); escolhe a face
        do objeto mais perto disso, para o pulso girar o mínimo."""
        p, q = self.pos_objeto(), self.pos_destino()
        # o pulso guarda o giro do objeto no mundo durante o transporte (girar com o objeto na mão
        # faz escorregar); mirando a meia distância entre o ângulo da pega e o do destino, o giro do
        # pulso fica pequeno nas duas pontas
        a1, a2 = np.arctan2(p[1], p[0]), np.arctan2(q[1], q[0])
        radial = a1 + _ang(a2 - a1) / 2
        R = self.d.xmat[self.obj].reshape(3, 3)
        tipo = self.m.geom_type[self.geom_obj]
        if tipo == mujoco.mjtGeom.mjGEOM_BOX:
            meia = self.m.geom_size[self.geom_obj]
            yaw = np.arctan2(R[1, 0], R[0, 0])
            cands = [(abs(_ang(yaw + k * np.pi / 2 - radial)), yaw + k * np.pi / 2, 2 * meia[k % 2])
                     for k in range(4)]
            _, ang, larg = min(cands)
        else:
            ang, larg = radial, 2 * self.raio
        return np.array([np.cos(ang), np.sin(ang), 0.0]), float(larg)

    def desloc_pegada(self) -> np.ndarray:
        """Da ponta ao centro do objeto: o objeto fica encostado (com folga) no dedo fixo."""
        r = self.robo
        z_local = r.dedo_fixo + self.largura / 2 + r.folga_dedo
        return self.R_alvo[:, 2] * z_local

    # ---------- controle ----------
    def erro_rot(self, d: mujoco.MjData | None = None) -> np.ndarray:
        Rc = (d or self.d).site_xmat[self.tcp].reshape(3, 3)
        return 0.5 * sum(np.cross(Rc[:, i], self.R_alvo[:, i]) for i in range(3))

    def ik(self, alvo: np.ndarray, amort: float = 1e-3) -> np.ndarray:
        """Um passo de IK diferencial (mínimos quadrados amortecidos) -> alvo de juntas.
        A IK roda sobre a postura COMANDADA (cópia só cinemática), não sobre a medida: o servo do
        SO-101 é rígido (kp ~1000 N·m/rad), a gravidade quase não deixa erro, e integrar o erro
        medido (como no Panda) fazia o braço oscilar."""
        m, k = self.m, self.dk
        k.qpos[self.qadr] = self.q_cmd
        mujoco.mj_kinematics(m, k)
        mujoco.mj_comPos(m, k)
        jp = np.zeros((3, m.nv)); jr = np.zeros((3, m.nv))
        mujoco.mj_jacSite(m, k, jp, jr, self.tcp)
        erro_p = alvo - k.site_xpos[self.tcp]
        # pesos da rotação: a inclinação do eixo da garra cede quando o braço não alcança; o giro em
        # torno desse eixo (de que lado a garra fecha) só depende do pulso e não pode ceder
        a = k.site_xmat[self.tcp].reshape(3, 3)[:, 0]
        W = PESO_ORIENTACAO * (np.eye(3) - np.outer(a, a)) + PESO_GIRO * np.outer(a, a)
        J = np.vstack([jp[:, self.dadr], W @ jr[:, self.dadr]])
        e = np.concatenate([erro_p, W @ self.erro_rot(k)])
        # junta encostada no limite e empurrada para fora sai do cálculo: as outras compensam
        # (a garra inclina um pouco) em vez de o braço parar longe do alvo
        lo, hi = m.jnt_range[self.juntas, 0], m.jnt_range[self.juntas, 1]
        livre = np.ones(self.n, bool)
        for _ in range(3):
            Jl = J * livre
            dq = np.linalg.solve(Jl.T @ Jl + amort * np.eye(self.n), Jl.T @ e) * livre
            preso = livre & (((self.q_cmd >= hi - 1e-3) & (dq > 0)) | ((self.q_cmd <= lo + 1e-3) & (dq < 0)))
            if not preso.any():
                break
            livre &= ~preso
        self.q_cmd = np.clip(self.q_cmd + np.clip(dq, -0.05, 0.05),
                             m.jnt_range[self.juntas, 0], m.jnt_range[self.juntas, 1])
        return self.q_cmd

    def erro_orientacao(self) -> float:
        """Ângulo (rad) entre a garra e a orientação pedida."""
        Rc = self.d.site_xmat[self.tcp].reshape(3, 3)
        cos = (np.trace(self.R_alvo.T @ Rc) - 1) / 2
        return float(np.arccos(np.clip(cos, -1.0, 1.0)))

    def mover_para(self, alvo_fn, garra: float, fase: Fase, tol: float, vel: float,
                   gravar, cond_extra=None) -> bool:
        """Persegue um alvo que é recalculado a cada passo (malha fechada)."""
        m, d = self.m, self.d
        dt_ctrl = 0.02
        sub = int(dt_ctrl / m.opt.timestep)
        fase.inicio = d.time
        ref = d.site_xpos[self.tcp].copy()
        erro = np.inf
        while d.time - fase.inicio < fase.max_s:
            alvo = alvo_fn()
            passo = alvo - ref
            dist = np.linalg.norm(passo)
            if dist > vel * dt_ctrl:  # limita a velocidade do ponto de referência
                passo = passo / dist * vel * dt_ctrl
            ref = ref + passo
            d.ctrl[self.atu] = self.ik(ref)
            d.ctrl[self.atu_garra] = garra
            for _ in range(sub):
                mujoco.mj_step(m, d)
            gravar(fase)
            erro = np.linalg.norm(alvo - d.site_xpos[self.tcp])
            if erro < tol and (cond_extra is None or cond_extra()):
                fase.fim = d.time
                return True
        fase.fim = d.time
        self.ultimo_erro = float(erro)
        return False

    def esperar(self, segundos: float, garra: float, fase: Fase, gravar) -> None:
        fixo = self.d.site_xpos[self.tcp].copy()
        fase.max_s = segundos
        self.mover_para(lambda: fixo, garra, fase, tol=-1, vel=0.5, gravar=gravar)

    def executar(self, gravar=lambda fase: None, altura_seg: float | None = None) -> Resultado:
        d, r = self.d, self.robo
        res = Resultado(False, "")
        altura_seg = r.altura_seg if altura_seg is None else altura_seg
        acima = np.array([0, 0, altura_seg])
        meia = self.meia_altura
        vel = r.vel
        # pega no máximo 3 cm abaixo do topo: objeto alto não pode entrar na palma da mão
        # esfera: a ponta desce abaixo do centro, para os dois dedos apertarem dos dois lados do equador
        # (o dedo móvel do SO-101 toca mais alto que o fixo)
        z_pega = max(-0.4 * self.raio, 0.008 - meia) if self.esfera else max(meia - self.topo_acima, 0.0)
        pega = lambda: self.pos_objeto() + np.array([0, 0, z_pega]) - self.desloc_pegada()

        plano = [
            ("aproximar", "ir para cima do objeto", "pegar", 4.0),
            ("descer", "descer até o objeto", "pegar", 3.0),
            ("fechar", "fechar a garra", "pegar", 1.0),
            ("subir", "levantar o objeto", "levar", 2.5),
            ("levar", "transportar até o destino", "levar", 4.0),
            ("baixar", "baixar sobre o destino", "soltar", 3.0),
            ("abrir", "abrir a garra", "soltar", 0.8),
            ("recuar", "recuar para cima", "soltar", 2.0),
        ]
        fases = {n: Fase(n, rot, s, t) for n, rot, s, t in plano}
        res.fases = list(fases.values())

        # o passo anterior pode ter deixado a garra torta: só desce depois de alinhar
        alinhado = lambda: (np.linalg.norm((pega() - self.d.site_xpos[self.tcp])[:2]) < 0.003
                            and self.erro_orientacao() < 0.12)  # longe da base, lá em cima, só chega inclinada; a descida endireita
        ok = self.mover_para(lambda: pega() + acima, self.aberta, fases["aproximar"], 0.006, vel * 1.6,
                             gravar, cond_extra=alinhado)
        if not ok:
            res.motivo = "não alcançou a posição acima do objeto"; return self._fim(res)
        ok = self.mover_para(pega, self.aberta, fases["descer"], 0.004, vel * 0.4, gravar)
        if not ok:
            res.motivo = f"não desceu até o objeto (erro {self.ultimo_erro*100:.1f} cm)"; return self._fim(res)
        self.esperar(0.8, self.fechada, fases["fechar"], gravar)
        if len(self.dedos_tocando()) < 2:
            res.motivo = "a garra fechou sem segurar o objeto"; return self._fim(res)
        res.eventos.append({"t": round(d.time, 3), "evento": "contato dos dois dedos com o objeto"})

        z0 = self.pos_objeto()[2]
        pega_fixo = d.site_xpos[self.tcp].copy()
        # sobe até passar da borda do destino antes de andar de lado (senão o objeto bate na parede)
        z_transp = self.topo_destino() + 0.015 + meia + (pega_fixo[2] - self.pos_objeto()[2])
        alto = pega_fixo + np.array([0, 0, max(altura_seg, z_transp - pega_fixo[2])])
        self.mover_para(lambda: alto, self.fechada, fases["subir"], 0.01, vel, gravar)
        if self.pos_objeto()[2] < z0 + 0.6 * altura_seg:
            res.motivo = "o objeto escorregou ao subir"; return self._fim(res)
        res.eventos.append({"t": round(d.time, 3), "evento": "objeto levantado da mesa"})

        # malha fechada: leva o OBJETO (medido) até o destino; a ponta segue com o desvio atual
        # o desvio ponta-objeto é medido uma vez, com o objeto já no ar: se fosse medido a cada passo,
        # um objeto escorregando para baixo puxaria o alvo para cima (realimentação positiva)
        desvio0 = d.site_xpos[self.tcp] - self.pos_objeto()
        desvio = lambda: desvio0
        # passa com o fundo do objeto 1,5 cm acima da borda: mais alto, o pulso do SO-101 não
        # consegue manter a garra para baixo
        def sobre():
            p = self.pos_destino() + desvio()
            p[2] = self.topo_destino() + 0.015 + meia + desvio()[2]
            return p
        inicio_levar = d.time
        for wp in self.desvios(self.pos_objeto()[:2], self.pos_destino()[:2]):
            def passagem(wp=wp):
                p = sobre()
                p[:2] = wp + desvio()[:2]
                return p
            fases["levar"].max_s = 4.0 - (d.time - inicio_levar)
            self.mover_para(passagem, self.fechada, fases["levar"], 0.02, vel * 1.4, gravar)
        fases["levar"].max_s = max(4.0 - (d.time - inicio_levar), 1.5)
        ok = self.mover_para(sobre, self.fechada, fases["levar"], 0.01, vel * 1.4, gravar)
        fases["levar"].inicio = inicio_levar
        if not ok or self.tocando() < 1:
            res.motivo = "perdeu o objeto no transporte"; return self._fim(res)
        if self.deitar:
            res.motivo = "deitar ainda não existe para o SO-101"; return self._fim(res)
        baixo = lambda: self.pos_destino() + np.array([0, 0, meia + 0.006]) + desvio()
        self.mover_para(baixo, self.fechada, fases["baixar"], 0.008, vel * 0.5, gravar)
        self.esperar(0.6, self.aberta, fases["abrir"], gravar)
        alto = d.site_xpos[self.tcp].copy() + np.array([0, 0, 0.08])
        # recua devagar nos primeiros centímetros para não arrastar o objeto junto
        perto = d.site_xpos[self.tcp].copy() + np.array([0, 0, 0.02])
        self.mover_para(lambda: perto, self.aberta, fases["recuar"], 0.005, 0.04, gravar)
        inicio_recuo = fases["recuar"].inicio
        self.mover_para(lambda: alto, self.aberta, fases["recuar"], 0.015, vel, gravar)
        fases["recuar"].inicio = inicio_recuo
        self.esperar(0.6, self.aberta, Fase("assentar", "esperar assentar", "soltar", 0.6), gravar)

        if self.dentro_do_destino():
            res.sucesso, res.motivo = True, "objeto dentro do destino"
            res.eventos.append({"t": round(d.time, 3), "evento": "sucesso verificado pela física"})
        else:
            res.motivo = "objeto caiu fora do destino"
        return self._fim(res)

    def topo_destino(self) -> float:
        """Altura que o objeto precisa vencer até o destino: a borda mais alta do recipiente e o
        topo do que já está dentro dele e perto do caminho em linha reta (m). O que está fora do
        recipiente o caminho contorna (`desvios`): passar por cima de uma bola de tênis já exige
        mais altura do que o SO-101 alcança com a garra para baixo."""
        gs = self._geoms_destino()
        if not gs:
            return float(self.d.xpos[self.alvo_corpo][2])
        topo = max(float(self.d.geom_xpos[g][2] + self._meia_z(g)) for g in gs)
        a, b = self.pos_objeto()[:2], self.pos_destino()[:2]
        for g in range(self.m.ngeom):
            corpo = int(self.m.geom_bodyid[g])
            if (corpo in (self.obj, self.alvo_corpo, 0) or self.m.body_jntnum[corpo] == 0
                    or not self.m.geom_contype[g] or not self._dentro(self.d.xpos[corpo])):
                continue
            p = self.d.geom_xpos[g][:2]
            t = np.clip(np.dot(p - a, b - a) / max(np.dot(b - a, b - a), 1e-9), 0, 1)
            if np.linalg.norm(a + t * (b - a) - p) < self.m.geom_rbound[g] + self.raio + 0.01:
                topo = max(topo, float(self.d.geom_xpos[g][2] + self._meia_z(g)))
        return topo

    def obstaculos(self) -> list[tuple[np.ndarray, float]]:
        """Objetos soltos fora do destino: (centro xy, raio no plano)."""
        obs = []
        for corpo in range(1, self.m.nbody):
            if corpo in (self.obj, self.alvo_corpo) or self.m.body_jntnum[corpo] == 0:
                continue
            if self._dentro(self.d.xpos[corpo]):
                continue
            gs = [g for g in range(self.m.ngeom) if self.m.geom_bodyid[g] == corpo and self.m.geom_contype[g]]
            if gs:
                raio = max(float(np.hypot(*self.m.geom_aabb[g][3:5])) for g in gs)
                obs.append((self.d.xpos[corpo][:2].copy(), raio))
        return obs

    def desvios(self, a: np.ndarray, b: np.ndarray, folga: float = 0.015) -> list[np.ndarray]:
        """Pontos de passagem (xy) para ir de a até b sem bater o objeto carregado em outro objeto
        da mesa: cada obstáculo perto da linha reta empurra o caminho para o lado de fora dele."""
        meu = float(np.hypot(*self.m.geom_aabb[self.geom_obj][3:5]))
        pontos = []
        for c, r in self.obstaculos():
            ab = b - a
            t = float(np.clip(np.dot(c - a, ab) / max(np.dot(ab, ab), 1e-9), 0, 1))
            perto = a + t * ab
            dist = float(np.linalg.norm(perto - c))
            livre = r + meu + folga
            if dist >= livre or t in (0.0, 1.0):
                continue
            lado = (perto - c) / dist if dist > 1e-6 else np.array([-ab[1], ab[0]]) / np.linalg.norm(ab)
            pontos.append((t, c + lado * livre))
        return [p for _, p in sorted(pontos, key=lambda x: x[0])]

    def _dentro(self, p: np.ndarray) -> bool:
        gs = self._geoms_destino()
        c = self.d.xpos[self.alvo_corpo]
        local = self.d.xmat[self.alvo_corpo].reshape(3, 3).T @ (p - c)
        base = self.m.geom_size[gs[0]]
        return abs(local[0]) < base[0] and abs(local[1]) < base[1] and local[2] < 0.12

    def _meia_z(self, g: int) -> float:
        R = self.d.geom_xmat[g].reshape(3, 3)
        return float(np.abs(R[2]) @ self.m.geom_size[g]) if self.m.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX else float(self.m.geom_rbound[g])

    def _geoms_destino(self) -> list[int]:
        return [g for g in range(self.m.ngeom) if self.m.geom_bodyid[g] == self.alvo_corpo]

    def dentro_do_destino(self) -> bool:
        """Dentro do recipiente E apoiado no fundo dele: em cima de outro objeto não conta."""
        p = self.pos_objeto()
        gs = self._geoms_destino()
        if not gs:
            return np.linalg.norm(p[:2] - self.d.xpos[self.alvo_corpo][:2]) < 0.05
        R = self.d.xmat[self.obj].reshape(3, 3)
        meia_z = float(np.abs(R[2]) @ self.m.geom_aabb[self.geom_obj][3:])
        fundo = float(self.d.geom_xpos[gs[0]][2] + self._meia_z(gs[0]))
        return self._dentro(p) and p[2] - meia_z - fundo < 0.012

    def _fim(self, res: Resultado) -> Resultado:
        res.duracao = round(self.d.time, 3)
        return res


def _tem_site(m, nome) -> bool:
    try:
        m.site(nome); return True
    except KeyError:
        return False


def _geoms_dos_dedos(m, robo: Robo = SO101) -> list[int]:
    ids = []
    for nome in robo.corpos_dedos:
        b = m.body(nome).id
        ids += [g for g in range(m.ngeom) if m.geom_bodyid[g] == b and m.geom_contype[g] | m.geom_conaffinity[g]]
    return ids


def ir_para_casa(m: mujoco.MjModel, d: mujoco.MjData, robo: Robo = SO101) -> None:
    mujoco.mj_resetData(m, d)
    for n, q in zip(robo.juntas, robo.casa):
        d.qpos[m.jnt_qposadr[m.joint(n).id]] = q
        d.ctrl[m.actuator(n).id] = q
    d.ctrl[m.actuator(robo.junta_garra).id] = robo.garra_aberta
    mujoco.mj_forward(m, d)
