"""Provar uma ação na simulação antes de mandar para o robô real.

1. planejar(): um modelo de linguagem (Codex pela assinatura) lê a cena e um pedido em português
   ("arrume a mesa: tudo que rola vai para a bandeja") e devolve um plano em passos pegar->destino.
2. provar(): o plano roda N vezes no gêmeo de simulação, cada vez com pequenas variações; só passa
   se a taxa de sucesso ficar acima do mínimo. O relatório diz qual passo falha e por quê.
"""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
from pathlib import Path

import mujoco
import numpy as np

from .cena2mjcf import compilar
from .episodios import variar
from .foto2cena import extrair_json
from .gerador import Gerador, ir_para_casa
from .robos import SO101

PROMPT_PLANO = """Você controla um braço robótico pequeno (SO-101: garra de até {garra:.0f} cm, carga de até {carga:.0f} g) diante desta mesa:
{cena}

Pedido do usuário: "{pedido}"

Monte um plano de passos pegar->destino usando SOMENTE os nomes de objetos acima. O destino de
cada passo precisa ser um objeto do tipo "recipiente". Não invente objetos; se o pedido for
impossível, devolva passos vazios e explique em "obs".
Responda SOMENTE com JSON: {{"passos": [{{"pegar": "", "destino": ""}}], "obs": ""}}"""


def planejar(cena: dict, pedido: str, modelo: str | None = None, timeout: int = 600, motor: str = "codex") -> dict:
    resumo = [{k: o[k] for k in ("nome", "tipo", "tamanho", "pos", "cor")} for o in cena["objetos"]]
    prompt = PROMPT_PLANO.format(cena=json.dumps(resumo, ensure_ascii=False), pedido=pedido,
                                 garra=SO101.abertura_max * 100, carga=SO101.carga_max * 1000)
    if motor in ("gemini", "openrouter"):
        from .foto2cena import perguntar
        plano = extrair_json(perguntar(motor, prompt, None, modelo))
        return _conferir_plano(cena, plano, pedido)
    if motor == "claude":
        from .foto2cena import perguntar_claude
        plano = extrair_json(perguntar_claude(prompt, None, modelo, timeout))
        return _conferir_plano(cena, plano, pedido)
    modelo = modelo or "gpt-6-luna"
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "plano.txt"
        from .foto2cena import args_esforco
        subprocess.run(["codex", "exec", "-m", modelo, "-s", "read-only", "--skip-git-repo-check",
                        *args_esforco("codex"), "-o", str(saida), "-"], input=prompt, text=True, capture_output=True,
                       timeout=timeout, cwd=tmp)
        if not saida.exists():
            raise RuntimeError("o Codex não devolveu o plano (confira `codex login`)")
        plano = extrair_json(saida.read_text(encoding="utf-8"))
    return _conferir_plano(cena, plano, pedido)


def _conferir_plano(cena: dict, plano: dict, pedido: str) -> dict:
    nomes = {o["nome"]: o for o in cena["objetos"]}
    for p in plano.get("passos", []):
        if p["pegar"] not in nomes or p["destino"] not in nomes:
            raise ValueError(f"plano cita objeto que não existe: {p}")
        if nomes[p["destino"]]["tipo"] != "recipiente":
            raise ValueError(f"destino não é recipiente: {p['destino']}")
    plano["pedido"] = pedido
    return plano


def marcar_deitar(cena: dict, passos: list[dict]) -> list[dict]:
    """Cilindro mais alto que o dobro da borda do recipiente vai deitado (lata em bandeja rasa)."""
    obj = {o["nome"]: o for o in cena["objetos"]}
    novos = [dict(p) for p in passos]
    for p in novos:
        o, r = obj[p["pegar"]], obj[p["destino"]]
        if o["tipo"] == "cilindro" and o["tamanho"][1] > 2 * r["tamanho"][2]:
            p.setdefault("deitar", True)
    return novos


def _largura(o: dict, eixo: int) -> float:
    """Quanto o objeto ocupa ao longo de um eixo do recipiente (caixa girada: a diagonal)."""
    t = o["tamanho"]
    if o["tipo"] == "caixa":
        return float(np.hypot(t[0], t[1]))
    return float(t[0])


def distribuir_vagas(cena: dict, passos: list[dict]) -> list[dict]:
    """Objetos que vão para o mesmo recipiente ganham lugares diferentes ao longo do lado maior,
    cada um ocupando a sua largura, com folgas iguais entre eles e as paredes.
    Se algum vai deitado (ao longo de x), as vagas ficam lado a lado em y."""
    obj = {o["nome"]: o for o in cena["objetos"]}
    por_destino: dict[str, list[dict]] = {}
    novos = [dict(p) for p in passos]
    for p in novos:
        por_destino.setdefault(p["destino"], []).append(p)
    for destino, lista in por_destino.items():
        n = len(lista)
        if n == 1:
            continue
        lx, ly = obj[destino]["tamanho"][0], obj[destino]["tamanho"][1]
        eixo = 1 if any(p.get("deitar") for p in lista) or ly > lx else 0
        interno = (lx if eixo == 0 else ly) - 2 * 0.006
        larg = [_largura(obj[p["pegar"]], eixo) for p in lista]
        folga = max((interno - sum(larg)) / (n + 1), 0.0)
        pos = -interno / 2
        for p, w in zip(lista, larg):
            pos += folga + w / 2
            p.setdefault("vaga", [round(pos, 4), 0.0] if eixo == 0 else [0.0, round(pos, 4)])
            pos += w / 2
    return novos


def rodar_plano(cena: dict, passos: list[dict], rng: np.random.Generator | None, forca: float = 1.0,
                tamanho: float = 0.0, pior_caso: bool = False) -> list:
    c = variar(cena, rng, forca, tamanho, pior_caso) if rng is not None else copy.deepcopy(cena)
    m, _ = compilar(c)
    d = mujoco.MjData(m)
    ir_para_casa(m, d)
    for _ in range(250):
        mujoco.mj_step(m, d)
    resultados = []
    for p in passos:
        g = Gerador(m, d, p["pegar"], p["destino"], vaga=tuple(p.get("vaga", (0.0, 0.0))),
                    deitar=bool(p.get("deitar")))
        r = g.executar()
        resultados.append({"passo": p, "sucesso": r.sucesso, "motivo": r.motivo})
        if not r.sucesso:
            break
    # um passo posterior pode derrubar o que já estava no lugar: confere tudo no fim
    for res in resultados:
        if res["sucesso"]:
            g = Gerador(m, d, res["passo"]["pegar"], res["passo"]["destino"])
            if not g.dentro_do_destino():
                res["sucesso"], res["motivo"] = False, "saiu do destino num passo seguinte"
    return resultados


def provar(cena: dict, passos: list[dict], n: int = 20, minimo: float = 0.9, semente: int = 0,
           log=print, tamanho: float = 0.0, pior_caso: bool = False) -> dict:
    """tamanho > 0: a física roda com objetos de tamanho diferente do medido (as vagas continuam
    calculadas sobre a medida), como acontece quando a visão erra a escala."""
    rng = np.random.default_rng(semente)
    por_passo = [{"passo": p, "ok": 0, "falhas": {}} for p in passos]
    completos = 0
    for i in range(n):
        res = rodar_plano(cena, passos, rng, tamanho=tamanho, pior_caso=pior_caso)
        tudo = len(res) == len(passos) and all(r["sucesso"] for r in res)
        completos += tudo
        for j, r in enumerate(res):
            if r["sucesso"]:
                por_passo[j]["ok"] += 1
            else:
                f = por_passo[j]["falhas"]
                f[r["motivo"]] = f.get(r["motivo"], 0) + 1
        log(f"  tentativa {i + 1:3d}/{n}: {'plano completo' if tudo else 'falhou no passo ' + str(len(res))}")
    taxa = completos / max(n, 1)
    return {"tentativas": n, "planos_completos": completos, "taxa": round(taxa, 3), "minimo": minimo,
            "aprovado": taxa >= minimo, "var_tamanho": tamanho, "pior_caso": pior_caso, "por_passo": por_passo}
