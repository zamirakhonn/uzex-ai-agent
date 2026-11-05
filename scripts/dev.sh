#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
trap 'kill $API_PID' EXIT
cd frontend
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run dev
