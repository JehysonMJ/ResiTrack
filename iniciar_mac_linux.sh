#!/usr/bin/env bash
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Instala Python 3 desde https://www.python.org/downloads/"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
( sleep 3; (open http://localhost:5000 2>/dev/null || xdg-open http://localhost:5000 2>/dev/null) ) &
python app.py
