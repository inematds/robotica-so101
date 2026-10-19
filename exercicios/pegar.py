"""Gerador guiado pela visão: o braço pega onde a CÂMERA disse que o objeto está.

O `Gerador` do real2sim lê a posição exata do objeto na física a cada passo. Aqui:
  - antes de pegar: posição, largura, forma e giro vêm da foto (`visao.Objeto`);
  - depois que os dois dedos seguram (no real: corrente/posição do servo da garra), o objeto
    anda junto com a garra (ponta + desvio medido no instante em que fechou);
  - a caixa vem da foto também; os outros objetos a contornar, idem.
O corpo do simulador só entra para a física sentir contato (dedos) e para conferir no fim.
"""
from __future__ import annotations

import mujoco
import numpy as np

from real2sim.gerador import Gerador, _ang
from real2sim.robos import SO101

from .visao import Caixa, Objeto


class GeradorVisao(Gerador):
    def __init__(self, m, d, corpo: str, est: Objeto, caixa: Caixa, outros: list[Objeto],
                 vaga=(0.0, 0.0), destino_corpo: str = "caixa"):
        self.est, self.caixa_est, self.outros = est, caixa, outros
        self.desvio_mao = None
        self.soltou = False
        super().__init__(m, d, corpo, destino_corpo, vaga=vaga)
        # o que a visão mediu substitui o que o modelo sabe do objeto
        self.meia_altura = self.meia_altura_eixo = est.largura / 2
        self.raio = est.largura / 2
        self.esfera = est.forma == "redondo"
        # abre só o necessário (largura + ~3,5 cm): aberta toda (11 cm) o dedo empurra a peça vizinha
        # e a bola rola para fora da mesa. Medido no modelo: ~8,8 cm de vão a 1,0 rad.
        self.aberta = float(np.clip(-0.17 + (est.largura + 0.035) * 13.3, 0.5, SO101.garra_aberta))
        self.fecha, self.largura = self._escolher_pegada()
        from real2sim.gerador import rot_garra
        self.R_alvo = rot_garra(self.fecha)

    # ---------- percepção ----------
    def _segurando(self) -> bool:
        return hasattr(self, "dedos") and len(self.dedos_tocando()) >= 2

    def pos_objeto(self) -> np.ndarray:
        ponta = self.d.site_xpos[self.tcp]
        if not self.soltou and self._segurando():
            if self.desvio_mao is None:
                self.desvio_mao = np.array(self.est.pos) - ponta
            return ponta + self.desvio_mao
        if self.desvio_mao is not None:  # já levou e soltou: fica onde soltou
            self.soltou = True
            return getattr(self, "_ultimo", np.array(self.est.pos))
        return np.array(self.est.pos, float)

    def pos_destino(self) -> np.ndarray:
        c = self.caixa_est
        return np.array([c.pos[0] + self.vaga[0], c.pos[1] + self.vaga[1], 0.012])

    def _escolher_pegada(self):
        p, q = np.array(self.est.pos), self.pos_destino()
        a1, a2 = np.arctan2(p[1], p[0]), np.arctan2(q[1], q[0])
        radial = a1 + _ang(a2 - a1) / 2
        if self.est.forma == "quadrado":
            yaw = self.est.yaw
            cands = [(abs(_ang(yaw + k * np.pi / 2 - radial)), yaw + k * np.pi / 2) for k in range(4)]
            _, ang = min(cands)
        else:
            ang = radial
        return np.array([np.cos(ang), np.sin(ang), 0.0]), float(self.est.largura)

    def obstaculos(self):
        obs = []
        for o in self.outros:
            if o is self.est or o.na_caixa:
                continue
            obs.append((np.array(o.pos[:2]), o.largura / 2 * 1.5))
        return obs

    def mover_para(self, alvo_fn, *a, **k):
        r = super().mover_para(alvo_fn, *a, **k)
        if self._segurando() and self.desvio_mao is not None:
            self._ultimo = self.pos_objeto()
        return r

    # ---------- conferência pela física (só para medir; o exercício confere de novo pela câmera) ----------
    def dentro_do_destino(self) -> bool:
        salvo = self.pos_objeto
        self.pos_objeto = lambda: self.d.xpos[self.obj].copy()
        try:
            return Gerador.dentro_do_destino(self)
        finally:
            self.pos_objeto = salvo


def corpo_mais_perto(m, d, est: Objeto) -> str:
    """Qual corpo do simulador corresponde à mancha vista (só a física precisa do nome)."""
    melhor, nome = 1e9, ""
    for b in range(1, m.nbody):
        if m.body_jntnum[b] == 0 or m.jnt_type[m.body_jntadr[b]] != mujoco.mjtJoint.mjJNT_FREE:
            continue
        dist = float(np.linalg.norm(d.xpos[b][:2] - np.array(est.pos[:2])))
        if dist < melhor:
            melhor, nome = dist, m.body(b).name
    if melhor > 0.03:
        raise RuntimeError(f"nenhum objeto da física perto de {est.nome} ({melhor * 100:.1f} cm)")
    return nome


def vagas(caixa: Caixa) -> list[tuple[float, float]]:
    """Lugares dentro da caixa: 2 x 2 se couber (caixa padrão 17 x 12 cm), senão 3 em fila."""
    lx, ly = caixa.tamanho[0] - 0.012, caixa.tamanho[1] - 0.012
    if min(lx, ly) >= 0.1:
        return [(sx * lx / 4, sy * ly / 4) for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1))]
    eixo = 0 if lx >= ly else 1
    passo = (lx if eixo == 0 else ly) / 3
    return [((k * passo, 0.0) if eixo == 0 else (0.0, k * passo)) for k in (0, -1, 1)]


def vaga_livre(caixa: Caixa, dentro: list[Objeto]) -> tuple[float, float]:
    """Primeiro lugar da caixa que a câmera vê vazio."""
    for v in vagas(caixa):
        p = np.array(caixa.pos[:2]) + v
        if all(np.linalg.norm(np.array(o.pos[:2]) - p) > 0.03 for o in dentro):
            return (round(float(v[0]), 4), round(float(v[1]), 4))
    return (0.0, 0.0)


def no_alcance(o: Objeto) -> str | None:
    r = float(np.hypot(*o.pos[:2]))
    if not SO101.alcance[0] <= r <= 0.30:
        return f"{o.nome} está a {r * 100:.0f} cm da base; eu alcanço de {SO101.alcance[0] * 100:.0f} a 30 cm"
    if o.largura > SO101.abertura_max:
        return f"{o.nome} tem {o.largura * 100:.0f} cm; minha garra abre até {SO101.abertura_max * 100:.0f} cm"
    return None
