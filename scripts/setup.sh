#!/usr/bin/env bash
set -euo pipefail
cd /workspace/cria-es
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
.venv/bin/python -c "import PIL, ctranslate2; assert 'int8' in ctranslate2.get_supported_compute_types('cpu')"
