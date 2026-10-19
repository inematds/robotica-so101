"""Mesas sorteadas para os exercícios: cubos de 3 cm e bolas de 4 cm coloridos + a caixa preta.

A cena sorteada existe só para montar a física; os exercícios NÃO leem as posições daqui:
quem diz onde está cada coisa é a câmera (`visao.perceber`).
"""
from __future__ import annotations

import numpy as np

CAIXA = {"nome": "caixa", "tipo": "recipiente", "tamanho": [0.17, 0.12, 0.03], "pos": [0.17, -0.17], "cor": "preto"}
CORES = ["vermelho", "azul", "verde", "amarelo", "laranja", "roxo"]
PECAS = {
    "cubo": {"tipo": "caixa", "tamanho": [0.03, 0.03, 0.03], "massa": 0.02},
    "bola": {"tipo": "esfera", "tamanho": [0.04], "massa": 0.025},
}


def peca(nome: str, forma: str, cor: str, pos, yaw: float = 0.0) -> dict:
    o = {"nome": nome, **PECAS[forma], "cor": cor, "pos": [round(float(pos[0]), 4), round(float(pos[1]), 4)]}
    if forma == "cubo":
        o["yaw"] = round(float(yaw), 3)
    return o


def lugares(rng: np.random.Generator, n: int, sep: float = 0.07) -> list[np.ndarray]:
    """n posições livres na área de trabalho (15–28 cm da base, à esquerda da caixa).
    No estande, essa área fica marcada com fita na mesa."""
    pts: list[np.ndarray] = []
    for _ in range(2000):
        if len(pts) == n:
            break
        p = np.array([rng.uniform(0.14, 0.29), rng.uniform(-0.04, 0.20)])
        if not 0.15 <= np.hypot(*p) <= 0.28:
            continue
        if all(np.linalg.norm(p - q) >= sep for q in pts):
            pts.append(p)
    if len(pts) < n:
        raise RuntimeError(f"não coube {n} peças na mesa")
    return pts


def mesa(pecas: list[tuple[str, str]], rng: np.random.Generator, fonte: str = "") -> dict:
    """pecas: [(forma, cor), ...] -> cena com a caixa."""
    pos = lugares(rng, len(pecas))
    objs = [peca(f"p{i}_{f}_{c}", f, c, p, rng.uniform(-0.7, 0.7)) for i, ((f, c), p) in enumerate(zip(pecas, pos))]
    return {"fonte": fonte or "mesa sorteada (exercícios do estande)",
            "mesa": {"largura": 0.8, "profundidade": 0.5, "centro_x": 0.22, "cor": "bege"},
            "objetos": objs + [dict(CAIXA)]}


def mesa_intruso(rng: np.random.Generator) -> tuple[dict, dict]:
    """3 peças iguais + 1 intrusa (cor diferente, ou forma diferente na mesma cor)."""
    cor = str(rng.choice(CORES))
    forma = str(rng.choice(list(PECAS)))
    if rng.random() < 0.5:
        outra = str(rng.choice([c for c in CORES if c != cor]))
        intrusa, regra = (forma, outra), "cor"
    else:
        intrusa, regra = ("bola" if forma == "cubo" else "cubo", cor), "forma"
    pecas = [(forma, cor)] * 3 + [intrusa]
    ordem = rng.permutation(4)
    pecas = [pecas[i] for i in ordem]
    c = mesa(pecas, rng, "intruso")
    nome_intrusa = c["objetos"][int(np.where(ordem == 3)[0][0])]["nome"]
    return c, {"intrusa": nome_intrusa, "regra": regra}


def mesa_bagunca(rng: np.random.Generator, n: int | None = None) -> dict:
    n = n or int(rng.integers(2, 4))
    cores = rng.permutation(CORES)[:n]
    return mesa([(str(rng.choice(list(PECAS))), str(c)) for c in cores], rng, "bagunça")


def montar(cena: dict, luz: float = 0.6):
    """Compila a cena, baixa a luz para a câmera não estourar (no real: exposição da câmera),
    põe o braço em casa e deixa a física assentar."""
    import mujoco
    from real2sim.cena2mjcf import compilar
    from .braco import estado_inicial
    m, _ = compilar(cena)
    m.light_diffuse[:] *= luz
    m.vis.headlight.ambient[:] = np.array(m.vis.headlight.ambient) * luz
    m.vis.headlight.diffuse[:] = np.array(m.vis.headlight.diffuse) * luz
    d = mujoco.MjData(m)
    estado_inicial(m, d)
    return m, d
