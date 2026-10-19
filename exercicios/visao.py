"""Visão do estande: uma câmera fixa olhando a mesa de cima -> lista do que está na mesa.

Só imagem RGB, como a câmera externa do kit. Nada aqui lê a posição dos objetos na física:
  1. separa os pixels coloridos do fundo (mesa bege, sombra, braço) pela saturação;
  2. classifica a cor pelo matiz (vermelho, laranja, amarelo, verde, azul, roxo);
  3. junta os pixels vizinhos em manchas (cada mancha = um objeto);
  4. a caixa de destino é a mancha PRETA grande;
  5. cada mancha vira um raio da câmera; o raio corta a mesa na altura estimada do objeto
     (o tamanho aparente dá a largura, e a altura de um objeto pequeno de estande é parecida
     com a largura) -> posição em metros no referencial do robô.
Forma: cantos (quadrado) ou redondo, pela razão área / círculo que envolve a mancha.

Câmera do simulador: intrínsecos e pose exatos do MuJoCo. Câmera real: homografia da mesa
(4 marcas medidas com fita) em `calibracao.json`; ver `CamReal`.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

# matiz (graus) de cada cor que a visão reconhece; a mesa bege e a bandeja cinza ficam de fora
MATIZ = {"vermelho": 3, "laranja": 32, "amarelo": 57, "verde": 128, "azul": 222, "roxo": 275}
FEMININO = {"vermelho": "vermelha", "amarelo": "amarela", "roxo": "roxa"}


@dataclass
class Objeto:
    cor: str
    forma: str                 # "quadrado" | "redondo"
    pos: list[float]           # x, y, z do centro (m, referencial do robô)
    largura: float             # m
    yaw: float = 0.0           # giro (só faz sentido para quadrado)
    pixels: int = 0
    caixa_px: list[int] = field(default_factory=list)  # x0, y0, x1, y1 na imagem
    na_caixa: bool = False

    @property
    def nome(self) -> str:
        if self.forma == "quadrado":
            return f"cubo {self.cor}"
        return f"bola {FEMININO.get(self.cor, self.cor)}"

    def dict(self) -> dict:
        d = asdict(self)
        d["nome"] = self.nome
        return d


@dataclass
class Caixa:
    pos: list[float]
    tamanho: list[float]       # x, y (m)
    caixa_px: list[int] = field(default_factory=list)


@dataclass
class Visao:
    objetos: list[Objeto]
    caixa: Caixa | None

    def fora_da_caixa(self) -> list[Objeto]:
        return [o for o in self.objetos if not o.na_caixa]

    def descrever(self) -> str:
        if not self.objetos:
            return "A mesa está vazia."
        fora = [o.nome for o in self.fora_da_caixa()]
        dentro = [o.nome for o in self.objetos if o.na_caixa]
        partes = []
        if fora:
            partes.append(f"Vejo {_lista(fora)} na mesa")
        if dentro:
            partes.append(f"{_lista(dentro)} já {'está' if len(dentro) == 1 else 'estão'} na caixa")
        return "; ".join(partes) + "."


def _lista(itens: list[str]) -> str:
    itens = [("um " if i.startswith("cubo") else "uma ") + i for i in itens]
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


# ---------------- cor ----------------

def hsv(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """RGB uint8 -> matiz (graus), saturação e valor (0..1)."""
    f = img.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    mx, mn = f.max(-1), f.min(-1)
    d = mx - mn + 1e-6
    h = np.where(mx == r, (g - b) / d % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0)
    return h, s, mx


def mascaras(img: np.ndarray) -> tuple[dict[str, np.ndarray], np.ndarray]:
    h, s, v = hsv(img)
    colorido = (s > 0.4) & (v > 0.18)
    # cada pixel colorido vai para a cor de matiz mais perto (até 40° de distância)
    nomes = list(MATIZ)
    dist = np.stack([np.abs((h - MATIZ[n] + 180) % 360 - 180) for n in nomes])
    perto = dist.argmin(0)
    ok = colorido & (dist.min(0) < 40)
    cores = {n: ok & (perto == i) for i, n in enumerate(nomes)}
    preto = (v < 0.42) & (s < 0.25)
    return cores, preto


def manchas(mask: np.ndarray, minimo: int) -> list[np.ndarray]:
    """Componentes conectados (vizinhança 4) com pelo menos `minimo` pixels -> lista de (N, 2) [linha, coluna]."""
    vis = np.zeros_like(mask, bool)
    H, W = mask.shape
    saida = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if vis[y0, x0]:
            continue
        fila, pts = deque([(y0, x0)]), []
        vis[y0, x0] = True
        while fila:
            y, x = fila.popleft()
            pts.append((y, x))
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not vis[yy, xx]:
                    vis[yy, xx] = True
                    fila.append((yy, xx))
        if len(pts) >= minimo:
            saida.append(np.array(pts))
    return saida


def forma_e_giro(pts: np.ndarray) -> tuple[str, float]:
    c = pts.mean(0)
    dist = np.hypot(*(pts - c).T)
    rmax = float(np.percentile(dist, 99.5)) + 0.5
    cheio = len(pts) / (np.pi * rmax ** 2)  # círculo ~0,95; quadrado ~0,64
    if cheio > 0.8:
        return "redondo", 0.0
    # quadrado: o canto é o ponto mais longe; o lado fica 45° antes. Imagem: linha = -x? (ver Camera.giro)
    canto = pts[np.argmax(dist)] - c
    return "quadrado", float(np.arctan2(canto[0], canto[1]))


# ---------------- câmeras ----------------

AREA = (0.0, 0.46, -0.34, 0.34)  # x0, x1, y0, y1 da área de trabalho na mesa (m)


class Camera:
    """Interface: foto() -> RGB uint8; para_mesa(u, v, z) -> ponto (x, y, z) no referencial do robô;
    metros_por_pixel(z) -> escala aproximada na altura z; giro(angulo_imagem) -> yaw no mundo."""

    def foto(self) -> np.ndarray: ...

    def para_mesa(self, u: float, v: float, z: float) -> np.ndarray: ...

    def metros_por_pixel(self, z: float) -> float: ...

    def giro(self, a: float) -> float: ...

    def para_pixel(self, x: float, y: float, z: float) -> tuple[float, float]: ...

    def area(self) -> np.ndarray:
        """Máscara da área de trabalho: fora dela (chão, borda da mesa) a visão não procura nada."""
        from PIL import Image, ImageDraw
        x0, x1, y0, y1 = AREA
        cantos = [self.para_pixel(x, y, 0.0) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        im = Image.new("L", (self.W, self.H), 0)
        ImageDraw.Draw(im).polygon(cantos, fill=1)
        return np.asarray(im, bool)


class CamSim(Camera):
    def __init__(self, m, d, nome: str = "cima", largura: int = 640, altura: int = 480):
        import mujoco
        self.m, self.d, self.nome = m, d, nome
        self.W, self.H = largura, altura
        self.r = mujoco.Renderer(m, altura, largura)
        cid = m.camera(nome).id
        self.cid = cid
        self.f = (altura / 2) / np.tan(np.radians(m.cam_fovy[cid]) / 2)

    def foto(self) -> np.ndarray:
        self.r.update_scene(self.d, self.nome)
        return self.r.render().copy()

    def _pose(self):
        return self.d.cam_xpos[self.cid].copy(), self.d.cam_xmat[self.cid].reshape(3, 3).copy()

    def para_mesa(self, u, v, z):
        p, R = self._pose()
        raio = R @ np.array([(u - self.W / 2) / self.f, -(v - self.H / 2) / self.f, -1.0])
        t = (z - p[2]) / raio[2]
        return p + t * raio

    def metros_por_pixel(self, z):
        p, _ = self._pose()
        return float((p[2] - z) / self.f)

    def para_pixel(self, x, y, z):
        p, R = self._pose()
        q = R.T @ (np.array([x, y, z]) - p)
        return (self.W / 2 + self.f * q[0] / -q[2], self.H / 2 - self.f * q[1] / -q[2])

    def giro(self, a):
        # imagem: coluna -> eixo x da câmera, linha -> -y da câmera
        p, R = self._pose()
        d = R @ np.array([np.cos(a), -np.sin(a), 0.0])
        return float(np.arctan2(d[1], d[0]))

    def fechar(self):
        self.r.close()


class CamReal(Camera):
    """Câmera USB fixa acima da mesa (NÃO testada no braço real ainda).

    calibracao.json: {"dispositivo": "/dev/video0", "largura": 640, "altura": 480,
                      "altura_camera": 0.85,
                      "pontos": [[u, v, x, y], ...]}   # >= 4 marcas na mesa, x/y medidos com fita (m)
    Homografia pixel -> mesa (z = 0); objetos com altura são corrigidos pela altura da câmera."""

    def __init__(self, calibracao: str | Path):
        c = json.loads(Path(calibracao).read_text(encoding="utf-8"))
        self.disp, self.W, self.H = c.get("dispositivo", "/dev/video0"), c["largura"], c["altura"]
        self.Hc = float(c["altura_camera"])
        p = np.array(c["pontos"], float)
        self.Hm = homografia(p[:, :2], p[:, 2:])
        meio = self.para_mesa(self.W / 2, self.H / 2, 0)
        self.centro = meio[:2]
        a, b = self.para_mesa(self.W / 2 + 50, self.H / 2, 0), meio
        self.mpp0 = float(np.linalg.norm(a - b) / 50)

    def foto(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as t:
            saida = Path(t) / "q.png"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "video4linux2", "-video_size",
                            f"{self.W}x{self.H}", "-i", self.disp, "-frames:v", "1", str(saida)], check=True)
            return np.asarray(Image.open(saida).convert("RGB"))

    def para_mesa(self, u, v, z):
        q = self.Hm @ np.array([u, v, 1.0])
        xy = q[:2] / q[2]
        # paralaxe: o topo de um objeto alto aparece mais longe do centro da câmera
        xy = self.centro + (xy - self.centro) * (self.Hc - z) / self.Hc if z else xy
        return np.array([xy[0], xy[1], z])

    def metros_por_pixel(self, z):
        return self.mpp0 * (self.Hc - z) / self.Hc

    def para_pixel(self, x, y, z):
        q = np.linalg.inv(self.Hm) @ np.array([x, y, 1.0])
        return (q[0] / q[2], q[1] / q[2])

    def giro(self, a):
        p0 = self.para_mesa(self.W / 2, self.H / 2, 0)
        p1 = self.para_mesa(self.W / 2 + 40 * np.cos(a), self.H / 2 + 40 * np.sin(a), 0)
        return float(np.arctan2(*(p1 - p0)[[1, 0]]))


def homografia(px: np.ndarray, mesa: np.ndarray) -> np.ndarray:
    """DLT: 4+ pares pixel -> mesa."""
    A = []
    for (u, v), (x, y) in zip(px, mesa):
        A.append([-u, -v, -1, 0, 0, 0, u * x, v * x, x])
        A.append([0, 0, 0, -u, -v, -1, u * y, v * y, y])
    _, _, vt = np.linalg.svd(np.array(A))
    Hm = vt[-1].reshape(3, 3)
    return Hm / Hm[2, 2]


# ---------------- percepção ----------------

def perceber(cam: Camera, img: np.ndarray | None = None, x_min: float = 0.10) -> Visao:
    """Uma foto -> objetos e caixa. x_min: na pose de foto o braço fica deitado na faixa x < 10 cm,
    rente à base; o que aparece ali é o próprio braço, não objeto."""
    img = cam.foto() if img is None else img
    cores, preto = mascaras(img)
    area = cam.area()
    cores = {k: v & area for k, v in cores.items()}
    preto = preto & area
    mpp = cam.metros_por_pixel(0.02)
    minimo = int((0.012 / mpp) ** 2)  # mancha menor que ~1,2 x 1,2 cm é ruído

    caixa = None
    pretas = [p for p in manchas(preto, minimo * 6)
              if cam.para_mesa(p[:, 1].mean(), p[:, 0].mean(), 0.0)[0] > x_min]
    if pretas:
        pts = max(pretas, key=len)
        # bordas da caixa: percentis para ignorar sombra solta
        y0, x0 = np.percentile(pts, 1, axis=0)
        y1, x1 = np.percentile(pts, 99, axis=0)
        a, b = cam.para_mesa(x0, y0, 0.0), cam.para_mesa(x1, y1, 0.0)
        centro = (a + b) / 2
        caixa = Caixa(pos=[round(float(centro[0]), 4), round(float(centro[1]), 4), 0.0],
                      tamanho=[round(float(abs(a[0] - b[0])), 4), round(float(abs(a[1] - b[1])), 4)],
                      caixa_px=[int(x0), int(y0), int(x1), int(y1)])

    objs = []
    for cor, mask in cores.items():
        for pts in manchas(mask, minimo):
            v, u = pts.mean(0)
            forma, ang = forma_e_giro(pts)
            # largura: círculo de mesma área (redondo) ou lado do quadrado
            area_px = len(pts)
            lado_px = np.sqrt(area_px / np.pi) * 2 if forma == "redondo" else np.sqrt(area_px)
            # o topo do objeto está mais perto da câmera e parece maior: corrige 2x pela altura
            larg, z = lado_px * mpp, 0.02
            for _ in range(3):
                larg = float(lado_px * cam.metros_por_pixel(larg))
                z = larg / 2
            # raio da câmera cortando a mesa a 3/4 da altura (o que a câmera vê é topo + um pouco do lado)
            p = cam.para_mesa(u, v, 1.5 * z)
            p[2] = z
            if p[0] < x_min:
                continue
            o = Objeto(cor=cor, forma=forma, pos=[round(float(c), 4) for c in p], largura=round(larg, 4),
                       yaw=round(cam.giro(ang) - np.pi / 4, 3) if forma == "quadrado" else 0.0,
                       pixels=int(area_px),
                       caixa_px=[int(pts[:, 1].min()), int(pts[:, 0].min()), int(pts[:, 1].max()), int(pts[:, 0].max())])
            if caixa is not None:
                dx, dy = abs(p[0] - caixa.pos[0]), abs(p[1] - caixa.pos[1])
                o.na_caixa = dx < caixa.tamanho[0] / 2 and dy < caixa.tamanho[1] / 2
            objs.append(o)
    objs.sort(key=lambda o: (o.pos[1], o.pos[0]))
    return Visao(objetos=objs, caixa=caixa)


def desenhar(img: np.ndarray, vis: Visao, destaque: Objeto | None = None):
    """Foto com o que a visão achou desenhado por cima (para o vídeo e para o painel do estande)."""
    from PIL import Image, ImageDraw
    from real2sim.filmar import _fonte
    im = Image.fromarray(img).convert("RGB")
    dr = ImageDraw.Draw(im)
    f = _fonte(max(12, img.shape[0] // 28))
    if vis.caixa:
        dr.rectangle(vis.caixa.caixa_px, outline=(250, 204, 21), width=3)
        dr.text((vis.caixa.caixa_px[0] + 4, vis.caixa.caixa_px[1] + 4), "CAIXA", font=f, fill=(250, 204, 21))
    for o in vis.objetos:
        cor = (255, 60, 60) if o is destaque else ((120, 220, 120) if o.na_caixa else (255, 255, 255))
        x0, y0, x1, y1 = o.caixa_px
        dr.rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), outline=cor, width=3 if o is destaque else 2)
        dr.text((x0, y1 + 4), o.nome, font=f, fill=cor)
    return im
