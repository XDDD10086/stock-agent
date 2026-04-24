# MILESTONES

## M0 - Environment Template and Secret Protection

- Start: 2026-04-17
- End: 2026-04-17
- Status: Completed

### Goals

- Add `.env.example` with the same key set as local `.env`.
- Keep real secrets in local `.env` only.
- Strengthen ignore rules to prevent accidental secret commits.

### Completed Work

- Created `.env.example` with placeholder values for sensitive keys.
- Updated `.gitignore` to include:
  - `.env`
  - `.env.*`
  - `!.env.example`
- Added decision record in `docs/DECISIONS.md`.

### Verification Evidence

- `.env.example` exists and includes required keys.
- `VALUECELL_BASE_URL` is not present in `.env` template and `VALUECELL_CHAT_URL` is used.
- `.gitignore` explicitly allows `.env.example` while ignoring other `.env*` files.

### Notes

- Git-specific checks (`git check-ignore`) will run after repository initialization.

---

## M1 - Core API Skeleton (8-hour run)

- Start: 2026-04-17
- End: 2026-04-17
- Status: Completed

### Goals

- Build FastAPI service skeleton with task creation and task query endpoints.
- Add SQLite-backed task persistence.
- Establish test baseline (TDD cycle) for task API behavior.

### Planned Deliverables

- `POST /tasks` creates task records with initial status.
- `GET /tasks/{task_id}` returns task details.
- `GET /tasks` returns task list ordered by creation time.
- Health endpoint returns service status.

### Execution Tracks

- Track A (Backend core): DB models, session, task service, API routes.
- Track B (Quality): API tests, fixture setup, smoke verification commands.

### Completed Work

- Added app skeleton: DB layer, task service, schema layer, `/tasks` routes, `/health` route, app factory.
- Added API tests covering create/get/list/health flows.
- Added and installed core dependencies for backend execution.

### Verification Evidence

- Command: `.venv/bin/python -m pytest tests/test_tasks_api.py -q`
- Result: `4 passed`
- Command: `.venv/bin/python -m pytest -q`
- Result: existing `test_valuecell.py` is interactive and fails collection under captured stdin; unrelated to M1 API baseline.

---

## M2 - Planning Contract Skeleton

- Start: 2026-04-17
- End: 2026-04-17
- Status: Completed

### Goals

- Add plan/review/execution pack schemas.
- Add planner/reviewer/finalizer service skeletons with strict schema validation.
- Add provider stubs and prompt templates for later API integration.

### Completed Work

- Added `PlanV1`, `ReviewV1`, and `ExecutionPack` schemas.
- Added `PlannerService`, `ReviewService`, and `FinalizeService`.
- Added `OpenAIClient` and `GeminiClient` stubs.
- Added prompt templates under `app/prompts/`.
- Added service contract tests.

### Completed Work (Prompt v2 Refresh)

- Upgraded planner/reviewer/finalizer prompts to v2:
  - stronger schema-only JSON constraints
  - explicit risk grading framing (Green/Yellow/Red)
  - few-shot examples to reduce output drift
- Updated `PROMPTS.md` to document v2 prompt expectations.

### Verification Evidence

- Command: `.venv/bin/python -m pytest tests/test_planning_services.py -q`
- Result: `3 passed`
- Command: `.venv/bin/python -m pytest tests -q`
- Result: `7 passed`
- Command: `.venv/bin/python -m pytest tests/test_live_provider_clients.py -q`
- Result: `2 passed`

---

## M3 - ValueCell Runner (Attach-Existing) Skeleton

- Start: 2026-04-17
- End: 2026-04-17
- Status: Completed

### Goals

- Build attach-existing runner contract aligned with dedicated real browser policy.
- Validate preflight policy checks before later CDP/browser integration.
- Define submission payload structure for execution handoff.

### Completed Work (Checkpoint 1)

- Added `RunnerConfig` and `ValueCellRunner` skeleton.
- Added preflight checks enforcing:
  - `execution_mode == attach_existing`
  - `failure_policy == manual_intervention`
  - required `chat_url` and `cdp_url`
- Added payload builder for execution submission input.
- Added runner contract tests.

### Completed Work (Checkpoint 2)

- Added executable runner flow with:
  - preflight gating
  - staged execution steps
  - failure fallback to `needs_manual_intervention`
  - screenshot/raw text artifact persistence
- Added synchronous orchestration service:
  - `plan_v1` / `review_v1` / `execution_pack` / `final_result` artifact writes
  - task status transitions (`created -> running -> completed|needs_manual_intervention`)
- Added task run/result API routes:
  - `POST /tasks/{task_id}/run`
  - `GET /tasks/{task_id}/result`
- Added `task_artifacts` DB table.

### Completed Work (Checkpoint 3)

- Added ValueCell raw text parser and integrated normalized summary/highlights/risk extraction.
- Added artifact query APIs:
  - `GET /tasks/{task_id}/artifacts`
  - `GET /tasks/{task_id}/artifacts/{artifact_type}`
- Added single-run concurrency guard:
  - concurrent `run` requests now return `409 runner is busy`.

### Completed Work (Checkpoint 4)

- Added live artifact inspection APIs:
  - `GET /tasks/{task_id}/artifacts`
  - `GET /tasks/{task_id}/artifacts/{artifact_type}`
- Added `USE_LIVE_LLM` toggle path and real OpenAI/Gemini provider implementations.
- Added JSON payload parsing utility for model outputs (plain JSON, fenced JSON, embedded JSON).

### Completed Work (Checkpoint 5)

- Added mocked live-provider integration tests for OpenAI/Gemini clients.
- Enforced JSON serialization contract in live provider input payloads.
- Expanded parser to extract markdown table rows into structured result `table`.

### Completed Work (Checkpoint 6)

- Hardened ValueCell DOM completion behavior:
  - added loading-state detection (`is_generation_in_progress`)
  - added meaningful-response gate (`has_meaningful_response`)
  - upgraded completion wait to stable polling before accepting final output
- Added targeted heuristic tests:
  - `tests/test_valuecell_heuristics.py`
  - `tests/test_valuecell_wait_logic.py`

### Completed Work (Checkpoint 7)

- Added persistent `runner_diagnostics` artifact to execution flow.
- Exposed diagnostics in existing artifact APIs without schema break:
  - `GET /tasks/{task_id}/artifacts`
  - `GET /tasks/{task_id}/artifacts/runner_diagnostics`
- Extended task API tests to assert diagnostics artifact presence and payload status.

### Completed Work (Checkpoint 8)

- Completed live CDP attach validation against dedicated Chrome session.
- Fixed live ValueCell DOM mismatch by anchoring assistant extraction to:
  - `main.main-chat-area > section`
  - assistant section after latest user section (`ml-auto`)
- Confirmed real `/run` path reaches `completed` with diagnostics artifact persisted.

### Verification Evidence

- Command: `.venv/bin/python -m pytest tests/test_valuecell_runner_contract.py -q`
- Result: `5 passed`
- Command: `.venv/bin/python -m pytest tests/test_valuecell_heuristics.py -q`
- Result: `3 passed`
- Command: `.venv/bin/python -m pytest tests/test_valuecell_wait_logic.py -q`
- Result: `2 passed`
- Command: `.venv/bin/python -m pytest tests/test_tasks_api.py -q`
- Result: `6 passed, 1 warning`
- Command: `.venv/bin/python -m pytest tests -q`
- Result: `29 passed, 1 warning`
- Command: `curl -s http://127.0.0.1:9222/json/version`
- Result: returns Chrome CDP metadata and `webSocketDebuggerUrl`
- Command: `POST /tasks -> POST /tasks/{task_id}/run` (live, port 8001)
- Result: `RUN_STATUS completed`, `DIAG_STATUS completed`, `DIAG_FAILED_STEP None`

### Remaining Work

- None.

---

## M4 - Scheduler API Baseline

- Start: 2026-04-17
- End: 2026-04-17
- Status: Completed

### Completed Work (Checkpoint 1)

- Added `schedules` persistence model.
- Added schedule service for create/list/pause/resume/delete.
- Added schedule API routes:
  - `POST /schedules`
  - `GET /schedules`
  - `POST /schedules/{id}/pause`
  - `POST /schedules/{id}/resume`
  - `DELETE /schedules/{id}`
- Added API test coverage for schedule CRUD flow.

### Completed Work (Checkpoint 2)

- Added Streamlit MVP control panel:
  - create task
  - run task
  - fetch result
  - create/pause/resume/delete schedule
  - refresh tasks/schedules and health check
- Frontend uses configurable `API_BASE_URL` (defaults to `http://127.0.0.1:8000`).

### Completed Work (Checkpoint 3)

- Wired optional APScheduler runtime behind `SCHEDULER_ENABLED` feature flag.
- Schedule create/pause/resume/delete now syncs to APScheduler job lifecycle when enabled.
- Scheduled jobs create and run tasks through the same orchestration pipeline.

### Completed Work (Checkpoint 4)

- Completed live cron execution validation with attached browser session.
- Verified schedule-created task lifecycle:
  - auto-created by scheduler
  - executed through same runner pipeline
  - reached final status `completed`
- Verified schedule smoke cleanup (`DELETE /schedules/{id}`).

### Verification Evidence

- Command: `.venv/bin/python -m pytest tests/test_schedules_api.py -q`
- Result: `1 passed`
- Command: `.venv/bin/python -m pytest tests -q`
- Result: `14 passed`
- Command: `.venv/bin/python -m py_compile app/providers/valuecell_runner.py app/routes/tasks.py app/routes/schedules.py app/orchestrator/execution_service.py`
- Result: `pass`
- Command: `POST /schedules` with cron `* * * * *` (live, port 8001)
- Result: `SCHEDULE_TRIGGERED True`, new task auto-created and finalized `completed`
- Command: `GET /tasks/{scheduled_task_id}/artifacts/runner_diagnostics`
- Result: `DIAG_STATUS completed`, `DIAG_FAILED_STEP None`

### Remaining Work

- None.

---

## M5 - Stabilization (Checkpoint)

- Start: 2026-04-17
- End: 2026-04-17
- Status: Completed

### Completed Work (Checkpoint 1)

- Added `pytest.ini` to scope default test discovery to `tests/`.
- Prevented interactive root scripts from breaking full test runs.

### Completed Work (Checkpoint 2)

- Added browser operations scripts:
  - `scripts/start_valuecell_browser.sh`
  - `scripts/check_cdp_connection.sh`
- Added `RUNBOOK.md` with end-to-end local operating procedure.
- Added `README.md` with current MVP status and startup path.
- Captured live CDP readiness blocker:
  - current endpoint `http://127.0.0.1:9222` returns `ECONNREFUSED` until dedicated browser starts with remote debugging.

### Completed Work (Checkpoint 3)

- Installed optional runtime dependencies:
  - `openai`
  - `google-genai`
  - `streamlit`
  - `playwright` (already available)
- Verified imports for optional stack.

### Completed Work (Checkpoint 4)

- Added project governance docs:
  - `AGENTS.md`
  - `ARCHITECTURE.md`
  - `TASKS.md`
  - `PROMPTS.md`
  - `SCHEDULER.md`
- Updated phase checklist with current completion status and pending live-validation items.

### Completed Work (Checkpoint 5)

- Polished Streamlit UI layout with:
  - visual theme and typography
  - tabbed workflow (`Task Studio` / `Schedule Desk` / `Monitor`)
  - operation cards, metrics, and improved error feedback

### Completed Work (Checkpoint 6)

- Added runbook-based live validation checklist to reduce handoff friction when CDP becomes available.
- Checklist now includes:
  - task run smoke path
  - artifact verification (including `runner_diagnostics`)
  - scheduler smoke run and evidence capture items

### Completed Work (Checkpoint 7)

- Resolved prior CDP blocker with active dedicated browser session.
- Verified end-to-end live execution and live scheduler trigger in same environment.

### Completed Work (Checkpoint 8)

- Added observability artifacts for execution telemetry:
  - `orchestration_metrics` (plan/review/finalize/runner/total seconds)
  - richer runner timing diagnostics (`duration_seconds`, `step_history`)
- Hardened parser quality for mixed-language output and noisy raw text:
  - Chinese summary/highlight/risk extraction
  - UI chrome noise filtering before extraction

### Completed Work (Checkpoint 9)

- Added pytest warning hygiene filter for known upstream deprecation in `google.genai.types`.
- Achieved clean full test output without warning noise.

### Completed Work (Checkpoint 10)

- Added MVP handoff automation scripts:
  - `scripts/run_api.sh`
  - `scripts/run_ui.sh`
  - `scripts/smoke_mvp.sh`
  - `scripts/smoke_mvp.py`
- Updated README/RUNBOOK to use script-based startup and one-command smoke acceptance.

### Notes

- A known `google.genai` deprecation warning is now filtered in pytest output for cleaner CI logs.

### Verification Evidence

- Command: `.venv/bin/python -m pytest -q`
- Result: `14 passed`
- Command: `.venv/bin/python - <<PY ... PlaywrightCdpAdapter.connect('http://127.0.0.1:9222') ... PY`
- Result: `CDP_CONNECT:FAIL (ECONNREFUSED)`
- Command: `.venv/bin/python - <<PY ... import streamlit, playwright, openai, google.genai ... PY`
- Result: `all available`
- Command: `.venv/bin/python -m pytest -q`
- Result: `21 passed, 1 warning`
- Command: `.venv/bin/python -m pytest -q`
- Result: `29 passed, 1 warning`
- Command: `rg "Live validation checklist" RUNBOOK.md`
- Result: `## 7. Live validation checklist (when browser is ready)`
- Command: `curl -s http://127.0.0.1:9222/json/version`
- Result: returns live CDP metadata with websocket debugger URL
- Command: `.venv/bin/python -m pytest tests/test_valuecell_parser.py -q`
- Result: `5 passed`
- Command: `.venv/bin/python -m pytest tests/test_valuecell_runner_contract.py -q`
- Result: `5 passed`
- Command: `.venv/bin/python -m pytest tests/test_tasks_api.py -q`
- Result: `6 passed, 1 warning`
- Command: `.venv/bin/python -m pytest -q`
- Result: `31 passed, 1 warning`
- Command: `.venv/bin/python -m pytest -q` (after warning filter)
- Result: `31 passed`
- Command: `./scripts/smoke_mvp.sh --base-url http://127.0.0.1:8000` (with API up + browser logged in)
- Result: all PASS checkpoints including task run and scheduler-triggered run

---

## M6 - Prompt Gate + Result Roundtrip + Scheduler Matrix

- Start: 2026-04-17
- End: 2026-04-17
- Status: Completed

### Completed Work (Checkpoint 1 - Prompt Gate)

- Added explicit review-gated prompt flow in orchestration:
  - `review.approved=true` -> direct finalization
  - `review.approved=false` -> single revision pass -> finalization
- Added `prompt_chain` artifact with full audit trail:
  - `user_intent`, `plan`, `review`, `revised_plan`, `final_prompt`, `review_gate_status`
- Extended `FinalResult` with:
  - `prompt_chain_status`

### Completed Work (Checkpoint 2 - ValueCell Raw Response Roundtrip)

- Runner now captures latest assistant response as primary raw source.
- Added fallback to full page text when latest assistant content is empty.
- Added `valuecell_raw_response` artifact and response field in `FinalResult`.
- Streamlit task view now shows:
  - structured result block (summary/table/risk)
  - expandable raw ValueCell response panel

### Completed Work (Checkpoint 3 - Scheduler Matrix)

- Expanded schedule trigger support to:
  - `cron`
  - `once`
  - `daily`
  - `weekly`
- Added schedule update and immediate execution APIs:
  - `PATCH /schedules/{id}`
  - `POST /schedules/{id}/run-once`
- Added one-time local-time handling:
  - input `run_at_local + timezone`
  - persisted `run_at_utc`
- Added idempotent SQLite compat migration for legacy DBs:
  - auto-add schedule columns `run_at_utc`, `time_of_day`, `days_of_week`

### Completed Work (Checkpoint 4 - LLM Mode + Completion Robustness)

- Added runtime LLM mode visibility to outputs/artifacts:
  - `FinalResult.llm_mode`
  - `prompt_chain.llm_mode`
- Upgraded deterministic fallback prompt generation to produce structured guidance prompt (non-pass-through).
- Hardened ValueCell completion logic:
  - ignores intermediate-progress text blocks
  - requires richer completion signals plus extra stability polling
  - ranks multiple assistant candidates and selects best-quality response
- Local manual-test profile updated to `USE_LIVE_LLM=true` for real OpenAI/Gemini verification.

### Completed Work (Checkpoint 5 - Live Failure Fallback)

- Added live-mode failure fallback to deterministic LLM chain for run continuity.
- Added fallback diagnostics and surfacing:
  - `llm_live_error` artifact
  - `prompt_chain.llm_fallback_reason`
  - `FinalResult.llm_fallback_reason`
- Streamlit result panel now warns when fallback is activated.

### Completed Work (Checkpoint 6 - Long Runtime UX + Send-Ready Gate)

- Added configurable long request timeout for Streamlit long-running actions:
  - `API_RUN_TIMEOUT_SECONDS` (default 1800)
- Updated Run/Result and Schedule Run-Once frontend calls to use long timeout.
- Hardened ValueCell completion gating:
  - final content must be present
  - input action must return to send-ready state (paper-plane), not stop-square

### Completed Work (Checkpoint 7 - Completion Action Bar Signal)

- Added ValueCell completion UI fallback signal from latest assistant reply action bar:
  - Chinese: `复制 / 保存 / 详情`
  - English: `Copy / Save / Details`
- Updated completion policy to accept:
  - send-ready state OR
  - reply action-bar visible
- Relaxed send-state detection from `visible+enabled` to `visible` to handle disabled paper-plane after answer is complete.
- Added wait-loop tests for completion-UI gating and capture-stage gating.

### Completed Work (Checkpoint 8 - Mixed Label Final Text Recognition)

- Fixed false-negative completion when final answer block contains both:
  - progress/thinking labels (for example `思考过程`)
  - final markers (`已完成任务/执行摘要/风险评级`)
- Updated final-candidate heuristics to prioritize completion markers over mixed-label noise.
- Verified on live attached ValueCell page: completion wait returns immediately when final block is already complete.

### Completed Work (Checkpoint 9 - M7 Committee Summarization Chain)

- Added post-ValueCell committee chain:
  - GPT-5.4 draft
  - Gemini 3.1 Pro review
  - GPT-5.4 finalize
- Extended final API payload with committee fields:
  - `committee_status`
  - `committee_summary`
  - `committee_actions`
  - `committee_fallback_reason`
- Added graceful degradation policy for committee errors:
  - task remains `completed`
  - committee status returns `fallback` with explicit reason
- Added skip policy for non-completed runs:
  - `committee_status=skipped_not_completed`
- Streamlit result panel upgraded:
  - committee output displayed first
  - legacy structured result and raw ValueCell content remain expandable
- Smoke validation upgraded to require `committee_chain` and `committee_result` artifacts.

### Completed Work (Checkpoint 10 - Committee Report Upgrade + Scheduler Trigger Expansion)

- Committee final output upgraded to report-mode contract:
  - `committee_report_json`
  - `committee_report_markdown`
- Finalizer prompt now enforces:
  - report-grade structure
  - key-number preservation
  - missing-data explicit declaration
  - 5-trading-day trigger/action framework
- Streamlit result panel now renders full committee markdown report in main result area.
- Scheduler trigger matrix expanded with:
  - `one-off` (alongside legacy `once`)
  - `interval` with `interval_minutes`
- APScheduler integration now supports `IntervalTrigger`.
- SQLite compat migration extended with:
  - `schedules.interval_minutes`
- Added API tests for:
  - `one-off` create flow
  - `interval` create/update flow
  - interval validation failure path

### Verification Evidence

- Command: `.venv/bin/python -m pytest tests/test_valuecell_runner_contract.py tests/test_tasks_api.py tests/test_schedules_api.py -q`
- Result: `16 passed`
- Command: `.venv/bin/python -m pytest tests/test_valuecell_heuristics.py tests/test_valuecell_wait_logic.py tests/test_tasks_api.py tests/test_schedules_api.py tests/test_valuecell_runner_contract.py -q`
- Result: `23 passed`
- Command: `.venv/bin/python -m pytest tests/test_valuecell_wait_logic.py tests/test_valuecell_heuristics.py tests/test_tasks_api.py -q`
- Result: `16 passed`
- Command: `.venv/bin/python -m pytest -q`
- Result: `39 passed`
- Command: `.venv/bin/python -m pytest -q`
- Result: `41 passed`
- Command: `.venv/bin/python -m pytest -q`
- Result: `42 passed`
- Command: `.venv/bin/python -m pytest -q`
- Result: `47 passed`
- Command: `./scripts/smoke_mvp.sh --skip-schedule-check --allow-manual-intervention` (API running, CDP attached)
- Result: all PASS checkpoints including committee artifact presence
- Command: `.venv/bin/python -m pytest -q`
- Result: `49 passed`

---

## M8 - Discord Dual-Channel Control Console

- Start: 2026-04-23
- End: 2026-04-23
- Status: Completed

### Goals

- Add a Discord bridge process that controls stock-agent through slash commands.
- Split command entry by channel:
  - analyst channel for `/run`
  - scheduler channel for `/schedule *`
- Unify all analysis outputs (manual + scheduled) to analyst result channel.
- Add scheduled-result dedupe state persistence outside Git tracking.

### Completed Work

- Added new bridge package under `app/discord_bridge`:
  - environment config loader
  - channel/role authorization policy
  - schedule target resolver (`id` first, unique name fallback)
  - API client wrapper for `/tasks` and `/schedules`
  - result formatter (embed/text)
  - service layer for command flows + schedule-result polling
  - persistent dedupe store (`DISCORD_DELIVERY_STATE_PATH`)
- Added Discord runtime entrypoint and launch script:
  - `app/discord_bridge/main.py`
  - `app/discord_bridge/runtime.py`
  - `scripts/run_discord_bridge.sh`
- Added schedule trigger metadata persistence for watcher routing:
  - scheduler callback now writes `trigger_meta` artifact (`source=schedule`)
  - `run-once` path writes `trigger_meta` (`source=schedule_run_once`)
- Added configuration/documentation updates:
  - `.env.example` Discord keys + watcher defaults
  - `README.md` and `RUNBOOK.md` Discord bridge usage notes
  - `.gitignore` explicit ignore for `data/discord_bridge_state.json`
  - optional dependency update for `discord.py`
- UX/stability polish after live Discord trial:
  - `/schedule create` handler now defers immediately and responds via follow-up to prevent "application did not respond"
  - run command pre-checks active running tasks and short-circuits with 409 busy message before creating orphan tasks
  - Streamlit `Schedule Desk` create flow simplified to three fields (`name`, `task description`, natural-language `trigger`) with shared parser logic
  - Discord bot switched to mention-only prefix mode to remove misleading privileged message-content warning for slash-command-only usage

### Verification Evidence

- Command: `.venv/bin/python -m pytest -q tests/test_discord_bridge_policy.py tests/test_discord_bridge_formatter.py tests/test_discord_bridge_service.py tests/test_discord_bridge_integration.py tests/test_schedules_api.py tests/test_tasks_api.py`
- Result: `26 passed`
- Command: `.venv/bin/python -m pytest -q tests`
- Result: `59 passed`
- Command: `.venv/bin/python -m pytest -q tests`
- Result: `73 passed`

### Notes

- ValueCell token-exhausted environments can still validate Discord flow using existing fake-adapter test path.
- Real Discord runtime requires optional dependency install including `discord.py`.

---

## M9 - Documentation, Deployment Guide, and Release Hygiene

- Start: 2026-04-23
- End: 2026-04-23
- Status: Completed

### Goals

- Deliver a complete project README that explains architecture, stack, features, and operations.
- Add dedicated documentation for deployment/operations and frontend-backend responsibilities.
- Run final regression tests and pre-push sensitive-information checks before GitHub submission.

### Completed Work

- Reworked `README.md` into a full operator/developer guide:
  - architecture overview
  - tech stack and feature matrix
  - startup modes and run scripts
  - Discord channel/permission model
  - testing and troubleshooting
  - security hygiene guidance
- Added dedicated deployment guide:
  - `docs/DEPLOYMENT.md`
  - install/start/stop/validation/backup/security checklist
- Added dedicated frontend-backend integration guide:
  - `docs/FRONTEND_BACKEND.md`
  - route/orchestrator/provider boundaries
  - Streamlit + Discord bridge interaction model
  - extension points and risk areas
- Updated `ARCHITECTURE.md` with deeper component boundaries, runtime flows, guardrails, and artifact model.
- Hardened flaky Discord watcher test data in `tests/test_discord_bridge_service.py` to use time-relative timestamps.

### Verification Evidence

- Command: `. .venv/bin/activate && python -m pytest -q tests`
- Result: `92 passed`
- Command: `rg -n "(OPENAI_API_KEY\\s*=\\s*sk-|GEMINI_API_KEY\\s*=\\s*AIza|DISCORD_BOT_TOKEN\\s*=\\s*[A-Za-z0-9_\\-]{20,}|xox[baprs]-|ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\\-]{20,})" --glob '!.venv/**' --glob '!data/**' --glob '!logs/**'`
- Result: `no matches`

### Notes

- README and docs now document the default Discord watcher knobs:
  - `DISCORD_TASK_WATCH_INTERVAL_SECONDS=5`
  - `DISCORD_TASK_WATCH_LOOKBACK_MINUTES=180`
  - `DISCORD_DELIVERY_STATE_PATH=./data/discord_bridge_state.json`
  - `DISCORD_HTTP_TIMEOUT_SECONDS=30`
