#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="${CHROME_USER_DATA_DIR:-/Users/bot/chrome-valuecell-profile}"
CDP_PORT="${CHROME_CDP_PORT:-9222}"

if [[ -d "/Applications/Google Chrome.app" ]]; then
  CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
elif [[ -d "/Applications/Google Chrome Canary.app" ]]; then
  CHROME_BIN="/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
else
  echo "Unable to find Google Chrome app under /Applications." >&2
  exit 1
fi

mkdir -p "${PROFILE_DIR}"

echo "Starting dedicated browser..."
echo "Profile: ${PROFILE_DIR}"
echo "CDP: http://127.0.0.1:${CDP_PORT}"

exec "${CHROME_BIN}" \
  --remote-debugging-port="${CDP_PORT}" \
  --user-data-dir="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  "https://valuecell.cn/zh/chat"
