"""Mede a visão contra a física: `python3 -m exercicios.medir_visao --n 20`.

Para cada mesa sorteada: foto da câmera de cima -> objetos achados; compara com a posição real
de cada corpo no simulador (que a visão não lê). Imprime erro médio e máximo (mm), acertos de cor
e de forma, objetos perdidos e inventados.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mujoco  # noqa: E402
import numpy as np  # noqa: E402

from exercicios.braco import pose_foto
from exercicios.mesa import mesa_bagunca, mesa_intruso
from exercicios.mesa import montar as montar_mesa  # noqa: E402
from exercicios.visao import CamSim, desenhar, perceber  # noqa: E402


def montar(cena):
    m, d = montar_mesa(cena)
    pose_foto(m, d)
    return m, d


def medir(n: int, semente: int = 0, foto: str | None = None) -> dict:
    rng = np.random.default_rng(semente)
    erros, cor_ok, forma_ok, perdidos, inventados, total = [], 0, 0, 0, 0, 0
    caixa_err = []
    for i in range(n):
        cena = mesa_intruso(rng)[0] if i % 2 == 0 else mesa_bagunca(rng, 3)
        m, d = montar(cena)
        cam = CamSim(m, d)
        img = cam.foto()
        vis = perceber(cam, img)
        if foto and i == 0:
            desenhar(img, vis).save(foto)
        reais = [o for o in cena["objetos"] if o["tipo"] != "recipiente"]
        usados = set()
        for o in reais:
            total += 1
            p = d.xpos[m.body(o["nome"]).id]
            cands = [(np.linalg.norm(np.array(v.pos[:2]) - p[:2]), k) for k, v in enumerate(vis.objetos) if k not in usados]
            if not cands or min(cands)[0] > 0.03:
                perdidos += 1
                continue
            dist, k = min(cands)
            usados.add(k)
            erros.append(dist)
            v = vis.objetos[k]
            cor_ok += v.cor == o["cor"]
            forma_ok += v.forma == ("quadrado" if o["tipo"] == "caixa" else "redondo")
        inventados += len(vis.objetos) - len(usados)
        if vis.caixa:
            caixa_err.append(np.linalg.norm(np.array(vis.caixa.pos[:2]) - d.xpos[m.body("caixa").id][:2]))
        else:
            caixa_err.append(np.inf)
        cam.fechar()
    e = np.array(erros) * 1000
    return {"mesas": n, "objetos": total, "erro_medio_mm": round(float(e.mean()), 2),
            "erro_max_mm": round(float(e.max()), 2), "cor_certa": f"{cor_ok}/{total}",
            "forma_certa": f"{forma_ok}/{total}", "perdidos": perdidos, "inventados": inventados,
            "caixa_erro_max_mm": round(float(max(caixa_err)) * 1000, 1)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--semente", type=int, default=0)
    ap.add_argument("--foto", default=None)
    r = medir(**vars(ap.parse_args()))
    for k, v in r.items():
        print(f"{k:18s} {v}")
