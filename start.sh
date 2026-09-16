#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null; then
  echo "Python 3 is required. Install it from https://www.python.org/downloads/"
  exit 1
fi
if ! command -v npm >/dev/null; then
  echo "Node.js (LTS) is required. Install it from https://nodejs.org/"
  exit 1
fi

if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
pip install -q -r backend/requirements.txt

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi

cleanup() { kill "${API_PID:-}" "${WEB_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
python -m uvicorn app.main:app --app-dir backend --reload --port 8000 &
API_PID=$!
(cd frontend && npm run dev) &
WEB_PID=$!
echo "\nManu AI is starting at http://localhost:3000"
echo "Press Ctrl+C to stop."
wait "$API_PID" "$WEB_PID"

