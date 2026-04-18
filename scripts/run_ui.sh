#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.optional.txt"
  exit 1
fi

# Load project .env for frontend runtime knobs when present.
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

. .venv/bin/activate

API_PORT_VALUE="${API_PORT:-8000}"
STREAMLIT_PORT_VALUE="${STREAMLIT_PORT:-8501}"
API_BASE_URL_VALUE="${API_BASE_URL:-http://127.0.0.1:${API_PORT_VALUE}}"
API_TIMEOUT_SECONDS_VALUE="${API_TIMEOUT_SECONDS:-90}"
API_RUN_TIMEOUT_SECONDS_VALUE="${API_RUN_TIMEOUT_SECONDS:-1800}"

exec env API_BASE_URL="$API_BASE_URL_VALUE" \
  API_TIMEOUT_SECONDS="$API_TIMEOUT_SECONDS_VALUE" \
  API_RUN_TIMEOUT_SECONDS="$API_RUN_TIMEOUT_SECONDS_VALUE" \
  streamlit run app/frontend/streamlit_app.py --server.port "$STREAMLIT_PORT_VALUE"
