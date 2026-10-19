"""Frase em português -> ação do braço, com a câmera achando o objeto citado.

Entendimento por regras, local e instantâneo (no estande não dá para esperar 30 s por uma IA
na nuvem, nem contar com internet). Frase que não casa com nada -> "não entendi" e o braço fica parado.

  pega / pegue / guarda / põe / coloca / bota  [o cubo vermelho]  -> guarda na caixa
  aponta / mostra / cadê / onde está           [a bola azul]      -> garra parada em cima dele
  acena / tchau / oi / olá                                        -> acena
  arruma / limpa / organiza                                       -> ordem de limpeza (arrumar)
  intruso / diferente                                             -> descobrir
  o que você vê / quantas / descreve                              -> fala o que vê
  descansa / volta / para / casa                                  -> posição de descanso
"""
from __future__ import annotations

import re
import unicodedata

from . import braco
from .atividades import Sessao, _art, arrumar, descobrir

CORES = {"vermelh": "vermelho", "azul": "azul", "azuis": "azul", "verde": "verde", "amarel": "amarelo",
         "laranj": "laranja", "rox": "roxo", "lilas": "roxo"}
FORMAS = {"cubo": "quadrado", "cubinho": "quadrado", "quadrad": "quadrado", "bloco": "quadrado", "dado": "quadrado",
          "bola": "redondo", "bolinha": "redondo", "esfera": "redondo", "redond": "redondo"}
ACOES = [
    ("descrever", r"\b(o que (voce|vc) (ve|esta vendo)|quant[ao]s?|descrev\w*|que tem na mesa)\b"),
    ("descobrir", r"\b(intrus\w*|diferente|nao combina)\b"),
    ("arrumar", r"\b(arrum\w*|limp\w*|organiz\w*|faxina)\b"),
    ("apontar", r"\b(apont\w*|mostr\w*|cade|onde (esta|fica)|indica\w*)\b"),
    ("pegar", r"\b(peg\w*|guard\w*|poe|ponha|coloc\w*|bot\w*|levant\w*|tira\w*|joga\w*)\b"),
    ("acenar", r"\b(acen\w*|tchau|oi|ola|da (um )?oi)\b"),
    ("casa", r"\b(descans\w*|volt\w*|para|pare|casa|repous\w*)\b"),
]


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", t)


def entender(frase: str) -> dict:
    """-> {"acao": ..., "cor": ... | None, "forma": ... | None}; acao None = não entendi."""
    t = normalizar(frase)
    acao = next((a for a, rx in ACOES if re.search(rx, t)), None)
    cor = next((v for k, v in CORES.items() if re.search(r"\b" + k, t)), None)
    forma = next((v for k, v in FORMAS.items() if re.search(r"\b" + k, t)), None)
    if acao is None and (cor or forma):
        acao = "pegar"  # "o cubo vermelho!" sozinho = pegar
    return {"acao": acao, "cor": cor, "forma": forma}


def _descreve_alvo(cor, forma) -> str:
    if forma == "quadrado":
        return f"cubo {cor}" if cor else "cubo"
    if forma == "redondo":
        from .visao import FEMININO
        return f"bola {FEMININO.get(cor, cor)}" if cor else "bola"
    return f"peça {cor}" if cor else "peça"


def executar(s: Sessao, frase: str) -> dict:
    """Entende a frase e faz. Devolve {"entendido": {...}, "fez": str, "sucesso": bool, "falas": [...]}."""
    ent = entender(frase)
    acao = ent["acao"]
    s.legenda = f"VOCÊ: {frase}"
    if s.grav:
        s.grav.segurar(1.2)
    if acao is None:
        s.falar("Não entendi. Tente: pega o cubo vermelho, aponta a bola azul, arruma a mesa ou dá tchau.")
        return {"entendido": ent, "fez": "nada", "sucesso": False, "falas": s.falas}
    if acao == "acenar":
        s.falar("Tchau, pessoal! Volte sempre." if "tchau" in normalizar(frase) else "Oi! Tudo bem?", 0.8)
        braco.acenar(s.m, s.d, s.gravar)
        braco.casa(s.m, s.d, s.gravar)
        return {"entendido": ent, "fez": "acenou", "sucesso": True, "falas": s.falas}
    if acao == "casa":
        braco.casa(s.m, s.d, s.gravar)
        s.falar("Voltei para a posição de descanso.")
        return {"entendido": ent, "fez": "casa", "sucesso": True, "falas": s.falas}
    if acao == "arrumar":
        r = arrumar(s)
        return {"entendido": ent, "fez": "arrumou", "sucesso": r["sucesso"], "falas": s.falas}
    if acao == "descobrir":
        r = descobrir(s)
        return {"entendido": ent, "fez": "descobriu", "sucesso": r["sucesso"], "falas": s.falas}

    vis = s.olhar()
    if acao == "descrever":
        s.falar(vis.descrever(), 2.4)
        return {"entendido": ent, "fez": "descreveu", "sucesso": True, "falas": s.falas}

    if not (ent["cor"] or ent["forma"]):
        s.falar("Qual peça? Diga a cor, por exemplo: pega o cubo vermelho.")
        return {"entendido": ent, "fez": "nada", "sucesso": False, "falas": s.falas}
    cands = [o for o in vis.fora_da_caixa()
             if (ent["cor"] is None or o.cor == ent["cor"]) and (ent["forma"] is None or o.forma == ent["forma"])]
    alvo_txt = _descreve_alvo(ent["cor"], ent["forma"])
    if not cands:
        s.falar(f"Não vejo nenhum {alvo_txt} fora da caixa." if not alvo_txt.startswith(("bola", "peça"))
                else f"Não vejo nenhuma {alvo_txt} fora da caixa.")
        braco.casa(s.m, s.d, s.gravar)
        return {"entendido": ent, "fez": "nada", "sucesso": False, "falas": s.falas}
    # mais de uma peça igual: a mais perto do robô
    o = min(cands, key=lambda x: x.pos[0] ** 2 + x.pos[1] ** 2)
    extra = f" Tem {len(cands)} iguais; vou na mais perto de mim." if len(cands) > 1 else ""
    s.destacar(o)
    if acao == "apontar":
        s.falar(f"Achei {_art(o)}. É {'este' if o.forma == 'quadrado' else 'esta'} aqui.{extra}", 1.0)
        s.apontar(o)
        return {"entendido": ent, "fez": "apontou", "sucesso": True, "alvo": o.nome, "falas": s.falas}
    s.falar(f"Entendido: vou guardar {_art(o)} na caixa.{extra}", 1.2)
    r = s.guardar(o, vis)
    s.falar("Feito!" if r["sucesso"] else f"Não consegui: {r['motivo']}.", 1.0)
    return {"entendido": ent, "fez": "guardou", "sucesso": r["sucesso"], "alvo": o.nome,
            "corpo": r.get("corpo"), "falas": s.falas}


# frases fixas do teste: (frase, ação, cor, forma, deve_mexer). Mesa do teste: cubo vermelho,
# bola azul, bola amarela, cubo verde. Não tem bola laranja: o certo é dizer que não vê e ficar parado.
FRASES_TESTE = [
    ("Pega o cubo vermelho e coloca na caixa", "pegar", "vermelho", "quadrado", True),
    ("guarda a bola azul", "pegar", "azul", "redondo", True),
    ("Robô, põe a bolinha amarela na caixa!", "pegar", "amarelo", "redondo", True),
    ("aponta o cubo verde", "apontar", "verde", "quadrado", True),
    ("cadê a bola laranja?", "apontar", "laranja", "redondo", False),
    ("o que você está vendo?", "descrever", None, None, True),
    ("dá tchau pro pessoal", "acenar", None, None, True),
    ("arruma a mesa", "arrumar", None, None, True),
    ("qual é o intruso?", "descobrir", None, None, True),
    ("volta pra casa", "casa", None, None, True),
    ("faz um bolo de chocolate", None, None, None, False),
]
