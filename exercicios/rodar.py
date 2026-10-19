"""Roda os exercícios em lote (taxa de acerto) ou uma vez com vídeo. Chamado pelo `r2s.py`.

Medida de acerto independente da câmera: no fim, a física do simulador diz o que está na caixa.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from real2sim.gerador import Gerador

from .atividades import Sessao, arrumar, conferir_fisica, descobrir
from .mesa import mesa, mesa_bagunca, mesa_intruso, montar
from .obedecer import FRASES_TESTE, entender, executar


def _na_caixa(m, d, corpo: str) -> bool:
    return bool(Gerador(m, d, corpo, "caixa").dentro_do_destino())


def lote_descobrir(n: int, semente: int = 0, video: str | None = None, falar=None) -> dict:
    rng = np.random.default_rng(semente)
    acertos, linhas = 0, []
    for i in range(n):
        cena, gab = mesa_intruso(rng)
        m, d = montar(cena)
        s = Sessao(m, d, video if (video and i == 0) else None, falar if n == 1 else None, "Exercício 1 · Descobrir o intruso")
        r = descobrir(s)
        s.fechar()
        ok = r["escolhido"] == gab["intrusa"] and _na_caixa(m, d, gab["intrusa"])
        acertos += ok
        linhas.append({"mesa": i, "intrusa": gab["intrusa"], "regra": gab["regra"], "escolheu": r["escolhido"],
                       "na_caixa": ok, "motivo": r["motivo"]})
        print(f"  mesa {i + 1:2d}/{n}: {'OK   ' if ok else 'FALHA'} intrusa={gab['intrusa']} ({gab['regra']}) escolheu={r['escolhido']}")
    return {"exercicio": "descobrir", "mesas": n, "acertos": acertos, "taxa": round(acertos / n, 3), "detalhe": linhas}


def lote_arrumar(n: int, semente: int = 0, video: str | None = None, falar=None) -> dict:
    rng = np.random.default_rng(semente)
    limpas, concorda, linhas = 0, 0, []
    for i in range(n):
        cena = mesa_bagunca(rng, 3 + (i % 2))
        m, d = montar(cena)
        s = Sessao(m, d, video if (video and i == 0) else None, falar if n == 1 else None, "Exercício 2 · Ordem de limpeza")
        r = arrumar(s)
        s.fechar()
        dentro, total = conferir_fisica(m, d)
        ok = dentro == total
        limpas += ok
        concorda += ok == r["sucesso"]
        linhas.append({"mesa": i, "pecas": total, "na_caixa": int(dentro), "robo_disse_limpa": r["sucesso"]})
        print(f"  mesa {i + 1:2d}/{n}: {'OK   ' if ok else 'FALHA'} {dentro}/{total} na caixa (robô disse: {'limpa' if r['sucesso'] else 'não limpa'})")
    return {"exercicio": "arrumar", "mesas": n, "limpas": limpas, "taxa": round(limpas / n, 3),
            "robo_concorda_com_a_fisica": concorda, "detalhe": linhas}


MESA_TESTE = [("cubo", "vermelho"), ("bola", "azul"), ("bola", "amarelo"), ("cubo", "verde")]


def mesa_teste(semente: int = 3) -> dict:
    return mesa(MESA_TESTE, np.random.default_rng(semente), "mesa fixa do teste de voz")


def teste_obedecer(semente: int = 3, video: str | None = None) -> dict:
    """Cada frase fixa numa mesa nova: entende certo E faz certo (conferido pela física)."""
    acertos, linhas = 0, []
    for k, (frase, acao, cor, forma, deve_mexer) in enumerate(FRASES_TESTE):
        ent = entender(frase)
        entendeu = (ent["acao"], ent["cor"], ent["forma"]) == (acao, cor, forma)
        if acao == "descobrir":
            cena, _ = mesa_intruso(np.random.default_rng(semente))
        else:
            cena = mesa_teste(semente)
        m, d = montar(cena)
        s = Sessao(m, d, video if (video and k == 0) else None, None, "Exercício 3 · Fale com o robô")
        r = executar(s, frase)
        s.fechar()
        fez = r["sucesso"]
        if not deve_mexer:  # não entendeu, ou não vê o que pediram: fala e fica parado
            fez = r["fez"] == "nada"
        elif acao == "pegar":
            fez = fez and _na_caixa(m, d, r.get("corpo", ""))
        elif acao == "arrumar":
            dentro, total = conferir_fisica(m, d)
            fez = dentro == total
        elif acao == "descrever":
            fez = all(n in r["falas"][-1] for n in ("cubo vermelho", "bola azul", "bola amarela", "cubo verde"))
        ok = entendeu and fez
        acertos += ok
        linhas.append({"frase": frase, "entendido": ent, "esperado": [acao, cor, forma, deve_mexer], "fez": r["fez"],
                       "ok": ok, "resposta": r["falas"][-1] if r["falas"] else ""})
        print(f"  {'OK   ' if ok else 'FALHA'} \"{frase}\" -> {ent['acao']} {ent['cor'] or ''} {ent['forma'] or ''} | {r['falas'][-1] if r['falas'] else ''}")
    return {"exercicio": "obedecer", "frases": len(FRASES_TESTE), "acertos": acertos,
            "taxa": round(acertos / len(FRASES_TESTE), 3), "detalhe": linhas}


def obedecer_uma(frases: list[str], semente: int = 3, video: str | None = None, falar=None, ouvir=None) -> dict:
    """Sessão contínua: várias frases seguidas na mesma mesa (como no estande)."""
    m, d = montar(mesa_teste(semente))
    s = Sessao(m, d, video, falar, "Exercício 3 · Fale com o robô")
    saidas = []
    try:
        if ouvir:
            while True:
                frase = ouvir()
                if not frase or "tchau robo" in frase.lower().replace("ô", "o"):
                    break
                saidas.append(executar(s, frase))
        for f in frases:
            saidas.append(executar(s, f))
    finally:
        s.fechar()
    return {"exercicio": "obedecer", "frases": [x["entendido"] for x in saidas], "falas": s.falas}


def salvar(rel: dict, arquivo: str | Path) -> None:
    Path(arquivo).parent.mkdir(parents=True, exist_ok=True)
    Path(arquivo).write_text(json.dumps(rel, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
