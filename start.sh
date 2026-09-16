#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null; then echo "Python 3 is required."; exit 1; fi
if ! command -v npm >/dev/null; then echo "Node.js is required."; exit 1; fi

if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
pip install -q -r backend/requirements.txt
if [ ! -d frontend/node_modules ]; then (cd frontend && npm install); fi

free_port() {
  local port="$1"
  while lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1; do port=$((port+1)); done
  echo "$port"
}

API_PORT="$(free_port 8000)"
WEB_PORT="$(free_port 3000)"
cleanup() { kill "${API_PID:-}" "${WEB_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

python -m uvicorn app.main_discovery:app --app-dir backend --reload --port "$API_PORT" &
API_PID=$!
(cd frontend && PORT="$WEB_PORT" NEXT_PUBLIC_API_URL="http://127.0.0.1:$API_PORT" npm run dev) &
WEB_PID=$!

echo ""
echo "✨ Manu AI is starting"
echo "   Web: http://localhost:$WEB_PORT"
echo "   API: http://127.0.0.1:$API_PORT/docs"
echo "   Ollama: http://127.0.0.1:11434"
echo ""
echo "Press Ctrl+C to stop."
wait "$API_PID" "$WEB_PID"
