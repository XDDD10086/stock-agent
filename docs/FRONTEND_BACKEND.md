# FRONTEND_BACKEND

This document describes how the frontend, backend, scheduler, and Discord bridge fit together.

## 1) Backend Responsibilities

Backend root: `app`

### 1.1 API layer

- `app/routes/tasks.py`
  - task create/list/get
  - run + result + artifact APIs
- `app/routes/schedules.py`
  - schedule CRUD + pause/resume/run-once
  - APScheduler sync hooks
- `app/routes/health.py`
  - service health endpoint

### 1.2 Orchestration layer

- `app/orchestrator/execution_service.py`
  - core run pipeline
  - single-run lock usage
  - artifact persistence and status transition
  - committee chain execution
- `app/orchestrator/schedule_service.py`
  - schedule validation and persistence logic
- `app/orchestrator/task_service.py`
  - task CRUD and artifact writes

### 1.3 Provider layer

- `app/providers/openai_client.py`
- `app/providers/gemini_client.py`
- `app/providers/valuecell_runner.py`

Key behavior:

- deterministic by default (`USE_LIVE_LLM=false`)
- live mode fallback to deterministic when provider fails
- ValueCell runner supports attach-existing browser policy and mock mode

### 1.4 Persistence and scheduler runtime

- `app/db/models.py` (tasks, artifacts, schedules)
- `app/scheduler/apscheduler_setup.py`

When `SCHEDULER_ENABLED=true`, schedule records are mirrored to APScheduler jobs.

---

## 2) Frontend (Streamlit)

Frontend root:

- `app/frontend/streamlit_app.py`
- `app/frontend/schedule_ui_helpers.py`

Tabs:

- `Task Studio`: create/run/fetch/artifacts
- `Schedule Desk`: create/manage schedules
- `Monitor`: snapshots and health checks

UX decisions:

- schedule creation uses exactly 3 fields:
  - `name`
  - `task description`
  - `trigger` (natural language)
- friendly handling for `409 runner is busy`
- long timeout for run/run-once (`API_RUN_TIMEOUT_SECONDS`, default 1800)
- active-running metric excludes stale running rows older than 30 minutes

---

## 3) Discord Bridge

Bridge root:

- `app/discord_bridge/main.py`
- `app/discord_bridge/runtime.py`
- `app/discord_bridge/service.py`

### 3.1 Command interfaces

- `/run prompt`
- `/schedule create`
- `/schedule list`
- `/schedule cancel target`
- `/schedule pause target`
- `/schedule resume target`
- `/schedule run-once target`

### 3.2 Routing and permissions

- run commands accepted only in configured run channels
- schedule commands accepted only in configured schedule channels
- role and admin checks via policy module

### 3.3 Unified analyst output

All analysis outputs are posted to `DISCORD_RESULT_CHANNEL_ID`:

- manual run final result
- schedule run-once result
- scheduled trigger completion result (from watcher)

Scheduler channel only receives schedule operation responses, not full analysis body.

### 3.4 Scheduled-result watcher

- polls `/tasks` and checks terminal statuses
- fetches `trigger_meta` to determine schedule source
- dedupes with `DISCORD_DELIVERY_STATE_PATH`

---

## 4) End-to-End Execution Flow

### 4.1 Manual run flow

1. User triggers run from UI/API/Discord.
2. Backend creates or resolves task.
3. `ExecutionService` executes:
   - planner -> reviewer -> finalizer
   - ValueCell execution
   - parser + committee chain
   - persist artifacts + final status
4. Result returned to caller and/or posted to Discord analyst channel.

### 4.2 Schedule flow

1. User creates schedule.
2. Schedule is stored in DB and mirrored to APScheduler if enabled.
3. Trigger fires and creates a task run via same execution path.
4. `trigger_meta` artifact is written.
5. Discord watcher finds completed scheduled task and posts to analyst channel.

---

## 5) Contracts and Key Data Fields

### 5.1 FinalResult highlights

Result payload includes:

- `task_id`
- `status`
- `summary`
- `highlights`
- `table`
- `risk_rating`
- `prompt_chain_status`
- `llm_mode`
- committee fields (`committee_status`, `committee_summary`, `committee_actions`, `committee_report_*`)

### 5.2 Schedule target resolution

For `/schedule cancel|pause|resume|run-once`:

- prefer numeric ID when target is numeric
- non-ID target resolves by unique name
- ambiguous name returns explicit error

---

## 6) Test Coverage Map

Representative modules:

- tasks/schedules API tests
- execution and provider behavior tests
- ValueCell parser and wait heuristics tests
- Discord bridge policy/service/runtime/config tests
- schedule trigger parser tests
- Streamlit schedule helper tests
- APScheduler setup tests

Run all:

```bash
pytest -q
```

---

## 7) Extension Guide

Low-risk extension points:

- add new schedule trigger parser patterns in `app/discord_bridge/schedule_trigger_parser.py`
- add new Discord commands in `app/discord_bridge/runtime.py`
- add new result panels in `app/frontend/streamlit_app.py`

Higher-risk areas (require extra regression testing):

- run lock and scheduler callback logic
- ValueCell runner completion heuristics
- artifact schema changes consumed by Discord watcher
