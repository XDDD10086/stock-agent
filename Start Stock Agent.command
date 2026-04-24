#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

./scripts/stack_ctl.sh start --open

echo
echo "stock-agent stack is up."
echo "Close this window when ready."
read -r -p "Press Enter to close..." _
