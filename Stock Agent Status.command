#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

./scripts/stack_ctl.sh status

echo
read -r -p "Press Enter to close..." _
