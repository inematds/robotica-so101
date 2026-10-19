"""Ouvir e falar, tudo local (sem nuvem, sem API).

  ouvir(segundos) -> texto   microfone via `arecord` + Whisper local (faster-whisper).
                             Instale com `./instalar.sh --voz`. Sem isso, use `--texto`.
  falar(texto)               voz pt-BR do Piper (`piper` + `aplay`), se existir; senão só imprime.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# vocabulário do estande: ajuda o Whisper a não trocar "cubo" por "cupom" etc.
DICA = ("Pedidos para um braço robô: pega o cubo vermelho, guarda a bola azul, aponta, cadê, "
        "arruma a mesa, dá tchau, oi robô.")
VOZ_PIPER = Path(os.environ.get("PIPER_VOZ", Path.home() / ".local/share/piper/pt_BR-faber-medium.onnx"))
_modelo = None


def transcrever(wav: str | Path, modelo: str = "small") -> str:
    global _modelo
    from faster_whisper import WhisperModel
    if _modelo is None or _modelo[0] != modelo:
        _modelo = (modelo, WhisperModel(modelo, device="auto", compute_type="auto"))
    segs, _ = _modelo[1].transcribe(str(wav), language="pt", vad_filter=True, initial_prompt=DICA)
    return " ".join(s.text for s in segs).strip()


def ouvir(segundos: float = 4.0, modelo: str = "small") -> str:
    try:
        import faster_whisper  # noqa: F401
    except ImportError as e:
        raise SystemExit("Para ouvir pelo microfone: ./instalar.sh --voz (Whisper local). "
                         "Ou digite: --texto \"pega o cubo vermelho\"") from e
    if not shutil.which("arecord"):
        raise SystemExit("arecord não encontrado (pacote alsa-utils)")
    with tempfile.TemporaryDirectory() as t:
        wav = Path(t) / "fala.wav"
        print(f"(ouvindo {segundos:.0f} s...)")
        subprocess.run(["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(int(segundos)), str(wav)],
                       check=True)
        texto = transcrever(wav, modelo)
    print("OUVI:", texto or "(nada)")
    return texto


def tem_voz() -> bool:
    return bool(shutil.which("piper")) and VOZ_PIPER.exists() and bool(shutil.which("aplay"))


def falar(texto: str) -> None:
    if not tem_voz():
        return
    with tempfile.TemporaryDirectory() as t:
        wav = Path(t) / "voz.wav"
        subprocess.run(["piper", "--model", str(VOZ_PIPER), "--output_file", str(wav)], input=texto.encode(),
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wav.exists():
            subprocess.run(["aplay", "-q", str(wav)], check=False)
