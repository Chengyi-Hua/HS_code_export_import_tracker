#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
printf 'Open http://127.0.0.1:8765 in your browser\n'
.venv/bin/python app.py
