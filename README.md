# stock-agent

`stock-agent` is a local orchestration system that combines:

- OpenAI (plan/finalize + committee draft/finalize)
- Gemini (review + committee review)
- ValueCell browser execution (attach to an existing logged-in browser session)
- FastAPI + SQLite task/schedule backend
- Streamlit operations console
- Discord dual-channel external control panel

It is designed for **single-session reliability first** (one browser session, one active run), with full artifact persistence for traceability.

## 1) What This Project Solves

- Run research tasks end-to-end from API, UI, or Discord.
- Persist every stage artifact (`plan_v1`, `review_v1`, `execution_pack`, `final_result`) for audit.
- Support scheduled runs (cron/one-off/daily/weekly/interval) via APScheduler.
- Keep Discord operations clean with channel split:
  - `#stock-analyst`: run + unified analysis results
  - `#stock-scheduler`: schedule management only
- Support a ValueCell quota-out mode (`VALUECELL_MOCK_MODE=pass`) so automation and integration can still be tested.

---

## 2) Architecture At a Glance

```text
Discord Slash Commands          Streamlit UI               API Clients
         |                          |                           |
         v                          v                           v
                 +----------------------------------+
                 | FastAPI (tasks / schedules)      |
                 | - task orchestration entry       |
                 | - schedule management API        |
                 +----------------+-----------------+
                                  |
                                  v
                 +----------------------------------+
                 | ExecutionService                  |
                 | plan -> review -> execution_pack |
                 | ValueCell run -> parse -> report |
                 | committee chain -> final_result  |
                 +----------------+-----------------+
                                  |
                +-----------------+------------------+
                |                                    |
                v                                    v
      ValueCellRunner (CDP attach)         SQLite (tasks/artifacts/schedules)
      - attach_existing only               + APScheduler jobs
      - manual_intervention on failure

Discord Bridge (separate process)
- Routes commands by channel/role
- Calls FastAPI locally
- Posts all analysis outputs to analyst channel
- Polls scheduled task results with dedupe state file
```

For deeper internals, see:

- `ARCHITECTURE.md`
- `docs/FRONTEND_BACKEND.md`
- `docs/DEPLOYMENT.md`

---

## 3) Tech Stack

- **Backend**: FastAPI, Pydantic, SQLAlchemy, Uvicorn
- **Storage**: SQLite (`data/app.db`)
- **Scheduler**: APScheduler (feature-flagged by `SCHEDULER_ENABLED`)
- **LLM Providers**: OpenAI Python SDK, Google GenAI SDK
- **Browser Runtime**: Playwright CDP attach to existing Chrome session
- **Frontend**: Streamlit
- **External Console**: `discord.py` slash commands
- **Testing**: Pytest (API, orchestration, scheduler, parser, bridge, UI helpers)
- **Ops Scripts**: bash scripts + one-command stack manager + macOS `.command` launchers

---

## 4) Core Features

### 4.1 Task orchestration

- `POST /tasks` create task
- `POST /tasks/{task_id}/run` execute full pipeline
- `GET /tasks/{task_id}/result` fetch normalized result
- Single-run guard: concurrent run returns `409 runner is busy`

### 4.2 Artifact persistence

Per run, artifacts include:

- `plan_v1`
- `review_v1`
- `execution_pack`
- `runner_diagnostics`
- `orchestration_metrics`
- `valuecell_raw_response`
- `committee_chain`
- `committee_result`
- `final_result`

### 4.3 Schedule management

Supported trigger types:

- `cron`
- `once` / `one-off`
- `daily`
- `weekly`
- `interval`

APIs:

- `POST /schedules`
- `GET /schedules`
- `PATCH /schedules/{id}`
- `POST /schedules/{id}/pause`
- `POST /schedules/{id}/resume`
- `POST /schedules/{id}/run-once`
- `DELETE /schedules/{id}`

### 4.4 Discord dual-channel control console

- Slash commands:
  - `/run prompt`
  - `/schedule create|list|cancel|pause|resume|run-once`
- Route constraints:
  - run command accepted only in `DISCORD_RUN_CHANNEL_IDS`
  - schedule commands accepted only in `DISCORD_SCHEDULE_CHANNEL_IDS`
- Unified result sink:
  - all analysis outputs (manual + scheduled) post to `DISCORD_RESULT_CHANNEL_ID`
- Scheduled-result watcher:
  - polls recent tasks
  - checks `trigger_meta`
  - dedupes by task id using `DISCORD_DELIVERY_STATE_PATH`

### 4.5 Streamlit operations console

Tabs:

- `Task Studio`
- `Schedule Desk`
- `Monitor`

Schedule creation UX uses only 3 inputs:

1. `name`
2. `task description`
3. `trigger` (natural language)

Natural-language trigger parsing is LLM-first with local fallback parser.

### 4.6 Token-exhausted ValueCell test mode

Set:

```bash
VALUECELL_MOCK_MODE=pass
```

Behavior:

- skips live ValueCell browser execution
- returns deterministic successful output
- keeps API/UI/Discord full workflow testable when ValueCell quota is unavailable

---

## 5) Repository Structure

```text
app/
  routes/                 # FastAPI routes (tasks/schedules/health)
  orchestrator/           # planning, review, execution, committee services
  providers/              # OpenAI, Gemini, ValueCell runner
  scheduler/              # APScheduler integration
  parsers/                # ValueCell text parsing
  frontend/               # Streamlit UI + schedule helper
  discord_bridge/         # Discord bot runtime/service/policy/client
  db/                     # SQLAlchemy models/session/migrations
scripts/                  # run/smoke/stack control scripts
tests/                    # end-to-end module coverage (pytest)
docs/                     # milestones, decisions, long-run board, deployment docs
```

---

## 6) Quick Start

### 6.1 Prerequisites

- Python 3.14 (project currently tested here)
- macOS/Linux shell environment
- Chrome installed (for ValueCell attach mode)

### 6.2 Install

```bash
cd /path/to/stock-agent
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements.optional.txt
```

### 6.3 Configure environment

```bash
cp .env.example .env
```

Then edit `.env`.

Minimum for API-only deterministic runs:

- `USE_LIVE_LLM=false`
- `SCHEDULER_ENABLED=true` (or false if you do not need scheduler runtime)

Minimum for live LLM:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `USE_LIVE_LLM=true`

Minimum for Discord bridge:

- `DISCORD_BOT_TOKEN`
- `DISCORD_APPLICATION_ID`
- `DISCORD_GUILD_ID`
- `DISCORD_ALLOWED_CHANNEL_IDS`
- `DISCORD_RUN_CHANNEL_IDS`
- `DISCORD_SCHEDULE_CHANNEL_IDS`
- `DISCORD_RESULT_CHANNEL_ID`

### 6.4 Start all services (recommended)

```bash
./scripts/stack_ctl.sh start --open
```

Check status:

```bash
./scripts/stack_ctl.sh status
```

Stop:

```bash
./scripts/stack_ctl.sh stop
```

Logs:

```bash
./scripts/stack_ctl.sh logs
```

### 6.5 Start services separately (optional)

```bash
./scripts/run_api.sh
./scripts/run_ui.sh
./scripts/run_discord_bridge.sh
```

### 6.6 macOS one-click launchers

- `Start Stock Agent.command`
- `Stop Stock Agent.command`
- `Stock Agent Status.command`

---

## 7) ValueCell Attach Mode

For real browser execution:

```bash
./scripts/start_valuecell_browser.sh
./scripts/check_cdp_connection.sh
```

Rules (enforced by runtime policy):

- execution mode must be `attach_existing`
- browser failure policy must be `manual_intervention`
- single active runner to protect shared browser session

---

## 8) Discord Permission Model (Team-safe)

Recommended with multi-user channel:

- keep `DISCORD_SCHEDULE_ALLOW_EVERYONE=false`
- set `DISCORD_SCHEDULE_MANAGER_ROLE_IDS` to a dedicated role
- optionally set `DISCORD_RUN_ROLE_IDS` for run command scope
- keep yourself in `DISCORD_ADMIN_USER_IDS` for override

Current permissive mode (your current setup) can still run:

- `DISCORD_SCHEDULE_ALLOW_EVERYONE=true`

but this is less strict for shared servers.

---

## 9) Testing

Run full suite:

```bash
pytest -q
```

Automation smoke against running API:

```bash
python scripts/e2e_automation_smoke.py --base-url http://127.0.0.1:8000
```

MVP smoke:

```bash
./scripts/smoke_mvp.sh
```

When ValueCell token is exhausted, use mock mode for E2E path verification:

```bash
VALUECELL_MOCK_MODE=pass
```

---

## 10) Troubleshooting

### `Run failed: runner is busy`

- Root cause: single-session guard is active (another run still `running`).
- Action: wait for current task completion, or clear stale run states and retry.

### Discord shows `This application did not respond`

- Usually from command timeout before response/defer.
- Current bridge uses defer/follow-up for schedule create to avoid this; verify bridge process is latest and running.

### Slash commands not visible

- Check `DISCORD_APPLICATION_ID`, `DISCORD_GUILD_ID`.
- Ensure bot is invited with `applications.commands` scope.
- Restart bridge and wait for command sync log.

### No scheduled result delivered to analyst channel

- Verify watcher is running in bridge.
- Verify `DISCORD_RESULT_CHANNEL_ID` and channel permissions.
- Verify task has `trigger_meta` artifact with schedule source.

### ValueCell unavailable but want to test flow

- Set `VALUECELL_MOCK_MODE=pass` and rerun API/UI/Discord integration tests.

---

## 11) Security and Secret Hygiene

- Keep real secrets only in local `.env`.
- `.env` and `.env.*` are git-ignored; only `.env.example` is tracked.
- Discord delivery dedupe state file is ignored:
  - `data/discord_bridge_state.json`
- Before every push, run secret scan checklist in:
  - `docs/DEPLOYMENT.md`

---

## 12) Additional Documentation

- Architecture: `ARCHITECTURE.md`
- Frontend/Backend deep dive: `docs/FRONTEND_BACKEND.md`
- Deployment and operations: `docs/DEPLOYMENT.md`
- Scheduler details: `SCHEDULER.md`
- Runtime runbook: `RUNBOOK.md`
- Decisions log: `docs/DECISIONS.md`
- Milestones archive: `docs/MILESTONES.md`
