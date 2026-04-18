# TASKS

## Phase 1 - Scaffold

- [x] Initialize FastAPI app skeleton
- [x] Create SQLite models/session setup
- [x] Add health and task APIs
- [x] Add env template and secret protection baseline

## Phase 2 - LLM Layer

- [x] Add plan/review/execution schemas
- [x] Add planner/reviewer/finalizer services
- [x] Add deterministic mode for local execution
- [x] Add live provider implementations (OpenAI/Gemini) behind `USE_LIVE_LLM`
- [x] Add live LLM integration tests with mocked API responses
- [x] Upgrade decision prompts to v2 (risk grading + few-shot examples)

## Phase 3 - Browser Layer

- [x] Add ValueCell runner preflight rules
- [x] Add execution flow skeleton with artifact persistence
- [x] Add parser-based final result normalization
- [x] Add single-run concurrency guard
- [x] Validate live CDP attach against dedicated browser session
- [x] Harden ValueCell-specific DOM completion heuristics

## Phase 4 - Result Layer

- [x] Persist `plan_v1` / `review_v1` / `execution_pack` / `final_result`
- [x] Add `GET /tasks/{task_id}/result`
- [x] Add artifact inspection endpoints
- [x] Add richer table extraction from raw ValueCell text
- [x] Add `orchestration_metrics` artifact (stage durations + total duration)
- [x] Improve parser for bilingual risk/summary extraction and UI noise filtering

## Phase 5 - Scheduler

- [x] Add schedule CRUD APIs
- [x] Add APScheduler runtime wiring behind `SCHEDULER_ENABLED`
- [x] Run live cron validation with attached browser session

## Phase 6 - Frontend and Ops

- [x] Add Streamlit MVP control panel
- [x] Add runbook and browser helper scripts
- [x] Add pytest discovery stabilization
- [x] Add polished frontend layout pass
- [x] Reduce third-party test warning noise for cleaner CI output
- [x] Add one-command startup and smoke scripts for MVP handoff
