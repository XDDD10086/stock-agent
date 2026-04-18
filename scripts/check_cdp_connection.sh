#!/usr/bin/env bash
set -euo pipefail

CDP_URL="${CHROME_CDP_URL:-http://127.0.0.1:9222}"

echo "Checking CDP endpoint: ${CDP_URL}"
if curl -sf "${CDP_URL}/json/version" >/dev/null; then
  echo "CDP check: OK"
else
  echo "CDP check: FAIL"
  exit 1
fi
