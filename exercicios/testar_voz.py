"""Teste do ouvido sem microfone: a voz do Piper fala 8 pedidos, o Whisper local transcreve e o
robô entende. `python3 -m exercicios.testar_voz [--modelo small|medium]` (precisa de ./instalar.sh --voz).

Medido em 19/10/2026: small 6–7/8 (varia entre rodadas), medium 7/8 (~3 s por frase). Erram as saudações curtas
("oi robô" vira "pai robô"); nesse caso o robô diz "não entendi" e não se mexe.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exercicios.obedecer import entender  # noqa: E402
from exercicios.voz import VOZ_PIPER, tem_voz, transcrever  # noqa: E402

FRASES = ["Pega o cubo vermelho e coloca na caixa", "Cadê a bola azul?", "Arruma a mesa", "Dá tchau pro pessoal",
          "Oi robô", "O que você está vendo?", "Guarda a bolinha amarela", "Aponta o cubo verde"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="small")
    a = ap.parse_args()
    if not tem_voz():
        sys.exit("precisa do piper + voz pt_BR + aplay")
    ok = 0
    with tempfile.TemporaryDirectory() as t:
        for i, f in enumerate(FRASES):
            wav = Path(t) / f"{i}.wav"
            subprocess.run(["piper", "--model", str(VOZ_PIPER), "--output_file", str(wav)], input=f.encode(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            ouvido = transcrever(wav, a.modelo)
            certo = entender(ouvido) == entender(f)
            ok += certo
            print(f"{'OK   ' if certo else 'ERRO '} {f!r} -> ouviu {ouvido!r}")
    print(f"voz ({a.modelo}): {ok}/{len(FRASES)} entendidas")
