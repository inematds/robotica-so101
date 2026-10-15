#!/usr/bin/env bash
# Instala o ambiente: venv com MuJoCo + modelo do SO-101 (MuJoCo Menagerie, Apache-2.0).
set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "--lerobot" ]; then   # venv opcional: exportar episódios para o LeRobot (r2s.py exportar)
  python3 -m venv .venv-lerobot
  .venv-lerobot/bin/pip install -q --upgrade pip
  .venv-lerobot/bin/pip install -q -r requirements-lerobot.txt
  .venv-lerobot/bin/python -c "import lerobot; print('LeRobot', lerobot.__version__, 'ok')"
  exit 0
fi

python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

if [ ! -f vendor/menagerie/robotstudio_so101/so101.xml ]; then
  git clone -q --depth 1 --filter=blob:none --sparse \
    https://github.com/google-deepmind/mujoco_menagerie.git vendor/menagerie
  git -C vendor/menagerie sparse-checkout set robotstudio_so101
fi

# sem monitor (servidor, WSL): renderiza pela GPU com EGL; troque por osmesa se não houver GPU
export MUJOCO_GL="${MUJOCO_GL:-egl}"
.venv/bin/python -c "import mujoco; print('MuJoCo', mujoco.__version__, 'ok')"
.venv/bin/python testes/rodar.py
