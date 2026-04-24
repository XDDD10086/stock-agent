# DEPLOYMENT

This document describes practical deployment and operations for `stock-agent`.

## 1) Deployment Targets

Current supported target is **local/self-hosted runtime**:

- FastAPI backend
- Streamlit frontend
- optional Discord bridge
- optional APScheduler runtime
- local SQLite storage

This project is optimized for a dedicated local machine or private VM where a ValueCell browser session can stay logged in.

---

## 2) Prerequisites

- Python 3.14
- `bash` shell
- Chrome (for ValueCell attach mode)
- Network access for model providers if `USE_LIVE_LLM=true`

Recommended machine baseline:

- 4+ CPU cores
- 8+ GB RAM
- stable network

---

## 3) Initial Installation

```bash
cd /path/to/stock-agent
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements.optional.txt
cp .env.example .env
```

Edit `.env`.

---

## 4) Environment Profiles

### 4.1 Safe local deterministic profile (no external LLM)

```bash
USE_LIVE_LLM=false
VALUECELL_MOCK_MODE=pass
```

Use this mode for E2E logic and automation validation when ValueCell quota or provider quotas are limited.

### 4.2 Live provider profile

Required:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `USE_LIVE_LLM=true`

Optional resilience knobs:

- `GEMINI_MODEL_FALLBACKS=gemini-2.5-pro,gemini-2.5-flash`

### 4.3 Discord profile

Required:

- `DISCORD_BOT_TOKEN`
- `DISCORD_APPLICATION_ID`
- `DISCORD_GUILD_ID`
- channel routing IDs

Recommended defaults already in `.env.example`:

- `DISCORD_TASK_WATCH_INTERVAL_SECONDS=5`
- `DISCORD_TASK_WATCH_LOOKBACK_MINUTES=180`
- `DISCORD_DELIVERY_STATE_PATH=./data/discord_bridge_state.json`
- `DISCORD_HTTP_TIMEOUT_SECONDS=30`

---

## 5) Start/Stop Operations

### 5.1 One-command stack control

```bash
./scripts/stack_ctl.sh start --open
./scripts/stack_ctl.sh status
./scripts/stack_ctl.sh stop
```

### 5.2 Individual services

```bash
./scripts/run_api.sh
./scripts/run_ui.sh
./scripts/run_discord_bridge.sh
```

### 5.3 macOS launchers

Double-click:

- `Start Stock Agent.command`
- `Stop Stock Agent.command`
- `Stock Agent Status.command`

---

## 6) Browser Attach Deployment

For live ValueCell execution, keep a dedicated browser session alive:

```bash
./scripts/start_valuecell_browser.sh
./scripts/check_cdp_connection.sh
```

Runtime guardrails:

- `BROWSER_EXECUTION_MODE=attach_existing`
- `BROWSER_FAILURE_POLICY=manual_intervention`
- single-run lock (`409 runner is busy`)

---

## 7) Health and Observability

- API health endpoint: `GET /health`
- Logs:
  - `logs/stack/api.log`
  - `logs/stack/ui.log`
  - `logs/stack/discord_bridge.log`
- Artifact inspection:
  - `GET /tasks/{task_id}/artifacts`
  - `GET /tasks/{task_id}/artifacts/{artifact_type}`

Important runtime artifacts:

- `runner_diagnostics`
- `orchestration_metrics`
- `final_result`
- `trigger_meta` (for schedule-origin runs)

---

## 8) Validation Checklist

### 8.1 Unit/integration test pass

```bash
pytest -q
```

### 8.2 E2E automation smoke

```bash
python scripts/e2e_automation_smoke.py --base-url http://127.0.0.1:8000
```

### 8.3 MVP smoke script

```bash
./scripts/smoke_mvp.sh
```

### 8.4 Discord verification

- in analyst channel: run `/run prompt:<text>`
- in scheduler channel:
  - `/schedule create`
  - `/schedule list`
  - `/schedule run-once`
- verify analysis result is posted to analyst channel only

---

## 9) Security and Secret Review Before Push

Run these checks before commit/push:

```bash
git status --short
rg -n "OPENAI_API_KEY|GEMINI_API_KEY|DISCORD_BOT_TOKEN|sk-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,}" -g'!*venv*' -g'!*.db' .
```

Review staged diff for accidental credentials:

```bash
git diff --staged
```

Rules:

- never commit `.env`
- only commit `.env.example`
- keep delivery state file out of git (`data/discord_bridge_state.json`)

---

## 10) Backup and Recovery

Backup directories:

- `data/` (SQLite)
- `artifacts/`
- `logs/` (optional)

Minimum backup command:

```bash
tar -czf stock-agent-backup-$(date +%Y%m%d-%H%M%S).tar.gz data artifacts
```

---

## 11) Known Operational Limits

- One active execution at a time (single browser session lock).
- Live ValueCell path depends on valid login/session state.
- Scheduler runtime is in-process; restarting API reloads jobs from DB via startup sync.

