# ARCHITECTURE

## 1) System Overview

`stock-agent` is a local orchestration platform with three entry surfaces:

- FastAPI endpoints
- Streamlit operations UI
- Discord slash commands (via optional bridge process)

All execution converges into the same backend pipeline and persists artifacts in SQLite.

Primary design principles:

- structured orchestration with auditable artifacts
- single-run safety for shared ValueCell browser session
- deterministic fallback paths for unstable external dependencies

---

## 2) Major Components

### 2.1 FastAPI service

Location:

- `/Users/bot/Projects/stock-agent/app/main.py`
- `/Users/bot/Projects/stock-agent/app/routes/`

Responsibilities:

- task CRUD/run/result/artifact endpoints
- schedule CRUD/pause/resume/run-once endpoints
- health endpoint

### 2.2 Orchestrator services

Location:

- `/Users/bot/Projects/stock-agent/app/orchestrator/`

Responsibilities:

- planner/reviewer/finalizer chain
- ValueCell execution orchestration
- committee post-processing
- artifact persistence and status transitions

### 2.3 Provider adapters

Location:

- `/Users/bot/Projects/stock-agent/app/providers/`

Responsibilities:

- OpenAI and Gemini model access (live or deterministic fallback)
- ValueCell browser execution via attach-existing CDP session

### 2.4 Storage and scheduler

Location:

- `/Users/bot/Projects/stock-agent/app/db/`
- `/Users/bot/Projects/stock-agent/app/scheduler/`

Responsibilities:

- SQLite persistence for tasks/artifacts/schedules
- APScheduler job mirroring (when `SCHEDULER_ENABLED=true`)

### 2.5 Streamlit frontend

Location:

- `/Users/bot/Projects/stock-agent/app/frontend/streamlit_app.py`

Responsibilities:

- operator UI for task run, result inspection, schedule management, health checks

### 2.6 Discord bridge (optional separate process)

Location:

- `/Users/bot/Projects/stock-agent/app/discord_bridge/`

Responsibilities:

- slash command registration and handling
- channel/role authorization
- API forwarding
- scheduled-result watcher + dedupe delivery

---

## 3) Runtime Data Flow

### 3.1 Task run flow

1. Task is created (`POST /tasks`) or selected.
2. `POST /tasks/{task_id}/run` acquires global run lock.
3. Orchestrator generates:
   - `plan_v1`
   - `review_v1`
   - `execution_pack`
4. ValueCell runner executes prompt in attached browser.
5. Raw output is parsed and normalized.
6. Committee chain produces report-grade recommendation output.
7. Artifacts and `final_result` are persisted.
8. Task status updates to `completed` or `needs_manual_intervention`.

### 3.2 Schedule flow

1. Schedule is created/updated through API.
2. Scheduler runtime mirrors record to APScheduler job.
3. Trigger callback creates a task and runs orchestration.
4. Callback writes `trigger_meta` artifact for route-aware downstream consumers.
5. Discord bridge watcher polls and forwards completed schedule results to analyst channel.

---

## 4) Concurrency and Guardrails

- `POST /tasks/{task_id}/run` is single-run guarded.
- If a run is active, API returns `409 runner is busy`.
- ValueCell runner policy:
  - `attach_existing` only
  - browser/session failures are `manual_intervention`
- Discord bridge also pre-checks for active runs to avoid creating orphan tasks.

---

## 5) Artifact Model

Core artifacts:

- `plan_v1`
- `review_v1`
- `execution_pack`
- `runner_diagnostics`
- `orchestration_metrics`
- `valuecell_raw_response`
- `committee_chain`
- `committee_result`
- `final_result`

Schedule-routing artifact:

- `trigger_meta` (`source`, `schedule_id`, `schedule_name`, timestamps)

Artifacts are the primary observability and audit interface for troubleshooting and downstream integrations.

---

## 6) Discord Channel Design

- Analyst channel(s): `/run` + all analysis outputs
- Scheduler channel(s): schedule lifecycle commands only
- Result sink: all analysis outputs posted to `DISCORD_RESULT_CHANNEL_ID`

This keeps command entry separated while unifying final decision output.

---

## 7) Failure Strategy

- Provider failures in live mode can fallback to deterministic chain.
- ValueCell runtime issues return `needs_manual_intervention` and keep diagnostics.
- Scheduled-result watcher uses durable dedupe state file to avoid duplicate messages.

---

## 8) Extensibility

Safe extension points:

- add new trigger parsing patterns
- add additional artifact types
- improve committee formatting
- extend Streamlit modules

Areas requiring extra caution:

- run lock semantics
- ValueCell completion heuristics
- scheduler callback behavior
