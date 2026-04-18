#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

. .venv/bin/activate

API_HOST_VALUE="${API_HOST:-0.0.0.0}"
API_PORT_VALUE="${API_PORT:-8000}"

exec uvicorn app.main:app --host "$API_HOST_VALUE" --port "$API_PORT_VALUE" --env-file .env
