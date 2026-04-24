#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs/stack"

API_PID_FILE="$RUN_DIR/api.pid"
UI_PID_FILE="$RUN_DIR/ui.pid"
DISCORD_PID_FILE="$RUN_DIR/discord_bridge.pid"

API_PATTERN="app.main:app"
UI_PATTERN="app/frontend/streamlit_app.py"
DISCORD_PATTERN="app.discord_bridge.main"

usage() {
  cat <<'EOF'
Usage: ./scripts/stack_ctl.sh <start|stop|restart|status|logs> [--open]

Commands:
  start      Start API + UI + Discord bridge (if DISCORD_BOT_TOKEN exists)
  stop       Stop managed processes
  restart    Restart managed processes
  status     Show managed process status
  logs       Tail all managed logs

Options:
  --open     Open API docs and Streamlit page after start
EOF
}

ensure_dirs() {
  mkdir -p "$RUN_DIR" "$LOG_DIR"
}

ensure_venv() {
  if [[ ! -d "$ROOT_DIR/.venv" ]]; then
    echo "Missing .venv. Run: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt"
    exit 1
  fi
}

pid_is_alive() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  kill -0 "$pid" >/dev/null 2>&1
}

find_matching_pids() {
  local pattern="$1"
  local raw
  raw="$(pgrep -f "$pattern" 2>/dev/null || true)"
  local filtered=()
  local pid
  for pid in $raw; do
    if [[ "$pid" == "$$" || "$pid" == "$PPID" ]]; then
      continue
    fi
    filtered+=("$pid")
  done
  if (( ${#filtered[@]} == 0 )); then
    return 0
  fi
  local first="true"
  for pid in "${filtered[@]}"; do
    if [[ "$first" == "true" ]]; then
      printf "%s" "$pid"
      first="false"
    else
      printf ",%s" "$pid"
    fi
  done
}

read_pid() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return 1
  fi
  tr -d '[:space:]' < "$pid_file"
}

is_running() {
  local pid_file="$1"
  local pid
  if ! pid="$(read_pid "$pid_file")"; then
    return 1
  fi
  if pid_is_alive "$pid"; then
    return 0
  fi
  rm -f "$pid_file"
  return 1
}

start_process() {
  local name="$1"
  local pid_file="$2"
  local log_file="$3"
  local command="$4"
  local pattern="$5"

  if is_running "$pid_file"; then
    local pid
    pid="$(read_pid "$pid_file")"
    echo "[$name] already running (pid=$pid)"
    return 0
  fi

  local unmanaged_pids
  unmanaged_pids="$(find_matching_pids "$pattern")"
  if [[ -n "$unmanaged_pids" ]]; then
    echo "[$name] already running outside stack_ctl (pid=$unmanaged_pids); skip duplicate start"
    return 0
  fi

  echo "[$name] starting..."
  nohup bash -lc "cd '$ROOT_DIR' && $command" >> "$log_file" 2>&1 &
  local pid=$!
  echo "$pid" > "$pid_file"
  sleep 0.2

  if pid_is_alive "$pid"; then
    echo "[$name] started (pid=$pid)"
    return 0
  fi

  echo "[$name] failed to start; check $log_file"
  return 1
}

stop_process() {
  local name="$1"
  local pid_file="$2"
  local pattern="$3"

  if ! is_running "$pid_file"; then
    local unmanaged_pids
    unmanaged_pids="$(find_matching_pids "$pattern")"
    if [[ -n "$unmanaged_pids" ]]; then
      echo "[$name] running (unmanaged) pid=$unmanaged_pids; stop manually or restart via stack_ctl once"
      return 0
    fi
    echo "[$name] not running"
    rm -f "$pid_file"
    return 0
  fi

  local pid
  pid="$(read_pid "$pid_file")"
  echo "[$name] stopping (pid=$pid)..."
  kill "$pid" >/dev/null 2>&1 || true

  local i
  for i in {1..30}; do
    if ! pid_is_alive "$pid"; then
      rm -f "$pid_file"
      echo "[$name] stopped"
      return 0
    fi
    sleep 0.2
  done

  echo "[$name] force stopping (pid=$pid)..."
  kill -9 "$pid" >/dev/null 2>&1 || true
  rm -f "$pid_file"
}

wait_for_api_health() {
  local retries=30
  local delay=0.5
  local api_port="${API_PORT:-8000}"
  local api_url="http://127.0.0.1:${api_port}/health"

  while (( retries > 0 )); do
    if curl -fsS -m 2 "$api_url" >/dev/null 2>&1; then
      echo "[api] health check ok ($api_url)"
      return 0
    fi
    retries=$((retries - 1))
    sleep "$delay"
  done

  echo "[api] health check did not pass yet; inspect $LOG_DIR/api.log"
  return 1
}

env_has_discord_token() {
  if [[ ! -f "$ROOT_DIR/.env" ]]; then
    return 1
  fi
  local token
  token="$(awk -F= '/^DISCORD_BOT_TOKEN=/{sub(/^ +/,"",$2); print $2}' "$ROOT_DIR/.env" | tail -n1)"
  [[ -n "${token}" ]]
}

do_start() {
  local open_pages="$1"

  ensure_dirs
  ensure_venv

  start_process "api" "$API_PID_FILE" "$LOG_DIR/api.log" ". .venv/bin/activate && exec uvicorn app.main:app --host \"${API_HOST:-0.0.0.0}\" --port \"${API_PORT:-8000}\" --env-file .env" "$API_PATTERN"
  wait_for_api_health || true

  start_process "ui" "$UI_PID_FILE" "$LOG_DIR/ui.log" "exec env STREAMLIT_SERVER_HEADLESS=true BROWSER_GATHER_USAGE_STATS=false ./scripts/run_ui.sh" "$UI_PATTERN"

  if env_has_discord_token; then
    start_process "discord_bridge" "$DISCORD_PID_FILE" "$LOG_DIR/discord_bridge.log" "exec ./scripts/run_discord_bridge.sh" "$DISCORD_PATTERN"
  else
    echo "[discord_bridge] skipped (DISCORD_BOT_TOKEN not set in .env)"
  fi

  if [[ "$open_pages" == "true" ]]; then
    local api_port="${API_PORT:-8000}"
    local streamlit_port="${STREAMLIT_PORT:-8501}"
    open "http://127.0.0.1:${api_port}/docs" >/dev/null 2>&1 || true
    open "http://127.0.0.1:${streamlit_port}" >/dev/null 2>&1 || true
  fi
}

do_stop() {
  ensure_dirs
  stop_process "discord_bridge" "$DISCORD_PID_FILE" "$DISCORD_PATTERN"
  stop_process "ui" "$UI_PID_FILE" "$UI_PATTERN"
  stop_process "api" "$API_PID_FILE" "$API_PATTERN"
}

do_status() {
  ensure_dirs

  print_one() {
    local name="$1"
    local pid_file="$2"
    local log_file="$3"
    local pattern="$4"
    if is_running "$pid_file"; then
      local pid
      pid="$(read_pid "$pid_file")"
      echo "[$name] running pid=$pid log=$log_file"
    else
      local unmanaged_pids
      unmanaged_pids="$(find_matching_pids "$pattern")"
      if [[ -n "$unmanaged_pids" ]]; then
        echo "[$name] running (unmanaged) pid=$unmanaged_pids log=$log_file"
      else
        echo "[$name] stopped log=$log_file"
      fi
    fi
  }

  print_one "api" "$API_PID_FILE" "$LOG_DIR/api.log" "$API_PATTERN"
  print_one "ui" "$UI_PID_FILE" "$LOG_DIR/ui.log" "$UI_PATTERN"
  print_one "discord_bridge" "$DISCORD_PID_FILE" "$LOG_DIR/discord_bridge.log" "$DISCORD_PATTERN"
}

do_logs() {
  ensure_dirs
  touch "$LOG_DIR/api.log" "$LOG_DIR/ui.log" "$LOG_DIR/discord_bridge.log"
  tail -n 80 -f "$LOG_DIR/api.log" "$LOG_DIR/ui.log" "$LOG_DIR/discord_bridge.log"
}

main() {
  local cmd="${1:-}"
  local open_pages="false"

  if [[ "${2:-}" == "--open" || "${1:-}" == "--open" ]]; then
    open_pages="true"
  fi

  case "$cmd" in
    start)
      do_start "$open_pages"
      do_status
      ;;
    stop)
      do_stop
      do_status
      ;;
    restart)
      do_stop
      do_start "$open_pages"
      do_status
      ;;
    status)
      do_status
      ;;
    logs)
      do_logs
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
