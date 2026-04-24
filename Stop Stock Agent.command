#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

./scripts/stack_ctl.sh stop

echo
echo "stock-agent stack stopped."
read -r -p "Press Enter to close..." _
