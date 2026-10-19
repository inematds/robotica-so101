"""As três atividades do estande, todas guiadas pela câmera de cima.

  descobrir  — olha a mesa, descobre o INTRUSO (a única peça de cor ou forma diferente), anuncia,
               pega, guarda na caixa e comemora.
  arrumar    — ordem de limpeza: tudo que a câmera vê fora da caixa vai para a caixa; olha de novo
               depois de cada peça e só para quando a mesa está limpa.
  obedecer   — uma frase (digitada ou falada) vira ação: pegar, apontar, acenar, arrumar, descrever.

Cada atividade devolve um relatório com o que o robô disse e fez; `Sessao` pode gravar MP4 com a
câmera geral, o que a visão viu (canto) e a fala na legenda.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

from real2sim.gerador import Gerador

from . import braco
from .pegar import GeradorVisao, corpo_mais_perto, no_alcance, vaga_livre
from .visao import CamSim, Objeto, Visao, desenhar, perceber


class Sessao:
    def __init__(self, m, d, video: str | Path | None = None, falar=None, titulo: str = ""):
        self.m, self.d = m, d
        self.cam = CamSim(m, d)
        self.falas: list[str] = []
        self.falar_fn = falar
        self.titulo = titulo
        self.ultima_visao = None
        self.legenda = ""
        self.grav = Gravador(m, d, video, self) if video else None

    # ---- utilidades ----
    def gravar(self, *_):
        if self.grav:
            self.grav.quadro()

    def falar(self, texto: str, segurar: float = 1.6) -> None:
        self.falas.append(texto)
        self.legenda = texto
        print("ROBÔ:", texto)
        if self.falar_fn:
            self.falar_fn(texto)
        if self.grav:
            self.grav.segurar(segurar)

    def olhar(self, destaque: Objeto | None = None) -> Visao:
        braco.pose_foto(self.m, self.d, self.gravar)
        img = self.cam.foto()
        vis = perceber(self.cam, img)
        self.ultima_visao = desenhar(img, vis, destaque)
        self._img, self._vis = img, vis
        if self.grav:
            self.grav.segurar(0.6)
        return vis

    def destacar(self, o: Objeto) -> None:
        self.ultima_visao = desenhar(self._img, self._vis, o)

    def guardar(self, o: Objeto, vis: Visao) -> dict:
        """Pega `o` (visto na foto) e põe numa vaga livre da caixa."""
        motivo = no_alcance(o)
        if motivo:
            return {"sucesso": False, "motivo": motivo}
        if vis.caixa is None:
            return {"sucesso": False, "motivo": "não vejo a caixa"}
        braco.casa(self.m, self.d, self.gravar)
        dentro = [x for x in vis.objetos if x.na_caixa]
        corpo = corpo_mais_perto(self.m, self.d, o)
        g = GeradorVisao(self.m, self.d, corpo, o, vis.caixa, vis.objetos, vaga=vaga_livre(vis.caixa, dentro))
        r = g.executar(self.gravar)
        braco.casa(self.m, self.d, self.gravar)
        return {"sucesso": r.sucesso, "motivo": r.motivo, "corpo": corpo}

    def apontar(self, o: Objeto) -> None:
        """Garra parada 7 cm acima do objeto (mostrar sem pegar)."""
        braco.casa(self.m, self.d, self.gravar)
        corpo = corpo_mais_perto(self.m, self.d, o)
        vis = self._vis
        g = GeradorVisao(self.m, self.d, corpo, o, vis.caixa, vis.objetos)
        from real2sim.gerador import Fase
        alvo = np.array(o.pos) + np.array([0, 0, 0.07])
        g.mover_para(lambda: alvo, 0.3, Fase("apontar", "apontar", "mostrar", 4.0), 0.008, 0.2, self.gravar)
        g.esperar(1.0, 0.3, Fase("mostrar", "mostrar", "mostrar", 1.0), self.gravar)
        braco.casa(self.m, self.d, self.gravar)

    def fechar(self) -> None:
        if self.grav:
            self.grav.fechar()
        self.cam.fechar()


# ------------------------------------------------------------------ descobrir

def achar_intruso(vis: Visao) -> tuple[Objeto | None, str]:
    objs = vis.fora_da_caixa()
    if len(objs) < 3:
        return None, "Preciso de pelo menos três peças na mesa para achar um intruso."
    cores = Counter(o.cor for o in objs)
    formas = Counter(o.forma for o in objs)
    unicas_cor = [o for o in objs if cores[o.cor] == 1]
    if len(unicas_cor) == 1 and len(cores) == 2:
        o = unicas_cor[0]
        resto = next(c for c in cores if c != o.cor)
        return o, f"Achei o intruso: {_art(o)}. Todas as outras peças são {_plural(resto, objs)}."
    unicas_forma = [o for o in objs if formas[o.forma] == 1]
    if len(unicas_forma) == 1 and len(formas) == 2:
        o = unicas_forma[0]
        return o, f"Achei o intruso: {_art(o)}. É a única {'redonda' if o.forma == 'redondo' else 'quadrada'}."
    return None, "Olhei bem e não tem um intruso só: tem mais de uma peça diferente."


def _art(o: Objeto) -> str:
    return ("o " if o.forma == "quadrado" else "a ") + o.nome


PLURAL = {"vermelho": "vermelhas", "azul": "azuis", "verde": "verdes", "amarelo": "amarelas",
          "laranja": "laranja", "roxo": "roxas"}


def _plural(cor: str, objs=None) -> str:
    return PLURAL.get(cor, cor)


def descobrir(s: Sessao) -> dict:
    s.falar("Vou olhar a mesa e descobrir qual peça não combina com as outras.")
    vis = s.olhar()
    o, frase = achar_intruso(vis)
    if o is None:
        s.falar(frase)
        return {"sucesso": False, "escolhido": None, "motivo": frase, "falas": s.falas}
    s.destacar(o)
    s.falar(frase, 2.4)
    s.falar(f"Vou tirar {_art(o)} da mesa e guardar na caixa.")
    r = s.guardar(o, vis)
    if r["sucesso"]:
        braco.bater_garra(s.m, s.d, s.gravar)
        s.falar("Pronto! Intruso guardado.", 1.0)
        braco.acenar(s.m, s.d, s.gravar)
        braco.casa(s.m, s.d, s.gravar)
    else:
        s.falar(f"Não consegui: {r['motivo']}.")
    return {"sucesso": r["sucesso"], "escolhido": r.get("corpo"), "cor": o.cor, "forma": o.forma,
            "motivo": r["motivo"], "falas": s.falas}


# ------------------------------------------------------------------ arrumar

def arrumar(s: Sessao, max_rodadas: int = 6) -> dict:
    s.falar("Ordem de limpeza recebida: tudo que estiver fora da caixa vai para a caixa.")
    guardados, falhas = [], []
    tentou: Counter = Counter()
    contagem = 0
    for _ in range(max_rodadas):
        vis = s.olhar()
        contagem = max(contagem, len(vis.objetos))
        if vis.caixa is None:
            s.falar("Não estou vendo a caixa. Coloque a caixa preta na mesa.")
            return {"sucesso": False, "guardados": guardados, "falas": s.falas}
        fora = [o for o in vis.fora_da_caixa() if tentou[(o.cor, o.forma)] < 2]
        if not fora:
            break
        # começa pela peça mais perto da caixa: o caminho das outras fica livre
        o = min(fora, key=lambda x: np.hypot(x.pos[0] - vis.caixa.pos[0], x.pos[1] - vis.caixa.pos[1]))
        s.destacar(o)
        n = len(vis.fora_da_caixa())
        s.falar(f"{'Vejo ' + str(n) + ' peças fora' if n > 1 else 'Falta uma peça'}. Agora {_art(o)}.", 1.2)
        tentou[(o.cor, o.forma)] += 1
        longe = no_alcance(o)
        if longe:
            tentou[(o.cor, o.forma)] = 2
            falhas.append(o.nome)
            s.falar(f"Não alcanço: {longe}. Chega mais perto de mim?", 1.6)
            continue
        r = s.guardar(o, vis)
        (guardados if r["sucesso"] else falhas).append(o.nome)
        if not r["sucesso"]:
            s.falar(f"Escapou: {r['motivo']}. Vou olhar de novo.", 1.2)
    vis = s.olhar()
    resto = vis.fora_da_caixa()
    sumiu = contagem - len(vis.objetos)
    if resto:
        s.falar(f"Não consegui guardar {', '.join(o.nome for o in resto)}.")
    elif sumiu > 0:
        s.falar(f"Contei {contagem} peças e agora vejo {len(vis.objetos)}: "
                f"{'uma caiu' if sumiu == 1 else str(sumiu) + ' caíram'} da mesa. Me ajuda a pegar?")
    else:
        s.falar("Mesa limpa! Tudo na caixa.", 1.0)
        braco.bater_garra(s.m, s.d, s.gravar)
    braco.casa(s.m, s.d, s.gravar)
    return {"sucesso": not resto and sumiu <= 0, "guardados": guardados, "falhas": falhas,
            "fora_no_fim": [o.nome for o in resto], "sumiram": max(sumiu, 0), "falas": s.falas}


def conferir_fisica(m, d) -> tuple[int, int]:
    """(dentro da caixa, total) pela física: a medida independente da câmera."""
    g = None
    total = dentro = 0
    for b in range(1, m.nbody):
        nome = m.body(b).name
        if not nome.startswith("p"):
            continue
        total += 1
        g = Gerador(m, d, nome, "caixa")
        dentro += g.dentro_do_destino()
    return dentro, total


# ------------------------------------------------------------------ Gravador

class Gravador:
    """MP4 30 fps: câmera geral, a foto da visão no canto e a fala do robô embaixo."""

    def __init__(self, m, d, arquivo, sessao: Sessao, largura=1280, altura=720, fps=30):
        import imageio.v2 as imageio
        import mujoco
        from real2sim.filmar import _fonte
        self.m, self.d, self.s = m, d, sessao
        self.W, self.H, self.fps = largura, altura, fps
        self.r = mujoco.Renderer(m, altura, largura)
        self.f1, self.f2 = _fonte(int(altura * 0.04)), _fonte(int(altura * 0.026))
        self.esc = imageio.get_writer(str(arquivo), fps=fps, codec="libx264", quality=8,
                                      macro_block_size=8, ffmpeg_params=["-pix_fmt", "yuv420p"])
        self.prox = 0.0
        self.ultimo = None

    def _tela(self):
        from PIL import Image, ImageDraw
        self.r.update_scene(self.d, "geral")
        tela = Image.fromarray(self.r.render())
        dr = ImageDraw.Draw(tela)
        if self.s.ultima_visao is not None:
            w = int(self.W * 0.3)
            h = int(w * 0.75)
            mini = self.s.ultima_visao.resize((w, h))
            x0, y0 = self.W - w - 16, 16
            dr.rectangle((x0 - 3, y0 - 3, x0 + w + 2, y0 + h + 2), fill=(250, 204, 21))
            tela.paste(mini, (x0, y0))
            dr.text((x0 + 8, y0 + h + 8), "o que a câmera vê", font=self.f2, fill=(250, 204, 21))
        if self.s.titulo:
            dr.text((24, 18), self.s.titulo, font=self.f2, fill=(250, 204, 21))
        dr.text((24, 18 + int(self.H * 0.04)), f"SO-101 · simulação MuJoCo · t = {self.d.time:5.1f} s",
                font=self.f2, fill=(235, 235, 235))
        if self.s.legenda:
            txt = self.s.legenda
            larg = dr.textlength(txt, font=self.f1)
            if larg > self.W - 80:  # quebra em duas linhas
                pal = txt.split()
                meio = len(pal) // 2
                linhas = [" ".join(pal[:meio]), " ".join(pal[meio:])]
            else:
                linhas = [txt]
            alt = int(self.H * 0.06)
            y = self.H - 24 - alt * len(linhas)
            lw = max(dr.textlength(t, font=self.f1) for t in linhas)
            dr.rounded_rectangle((20, y - 10, 50 + lw, self.H - 20), radius=10, fill=(12, 12, 16))
            for i, t in enumerate(linhas):
                dr.text((36, y + i * alt), t, font=self.f1, fill=(250, 204, 21))
        return np.asarray(tela)

    def quadro(self):
        if self.d.time < self.prox:
            return
        self.prox += 1.0 / self.fps
        self.ultimo = self._tela()
        self.esc.append_data(self.ultimo)

    def segurar(self, segundos: float):
        q = self._tela()
        for _ in range(int(segundos * self.fps)):
            self.esc.append_data(q)

    def fechar(self):
        self.segurar(1.0)
        self.esc.close()
        self.r.close()
