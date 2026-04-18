# ARCHITECTURE

## Overview

The system is a local FastAPI orchestrator with a deterministic-by-default LLM layer, browser runner integration, artifact persistence, scheduler API, and Streamlit operator UI.

## Components

- FastAPI app
  - `tasks` routes
  - `schedules` routes
  - `health` route
- Orchestrator services
  - task service
  - planning/review/finalize services
  - execution service
  - schedule service
- Providers
  - OpenAI client (live mode)
  - Gemini client (live mode)
  - ValueCell runner
- Parsers
  - ValueCell raw text parser
- Storage
  - SQLite tables: `tasks`, `task_artifacts`, `schedules`
- Scheduler
  - APScheduler runtime (feature-flagged)
- Frontend
  - Streamlit MVP control panel

## Data Flow

1. `POST /tasks` creates a task.
2. `POST /tasks/{task_id}/run`:
   - generate `plan_v1`
   - generate `review_v1`
   - generate `execution_pack`
   - execute ValueCell runner
   - normalize to `final_result`
   - persist all artifacts
3. `GET /tasks/{task_id}/result` returns latest normalized result.
4. Artifact introspection uses `/tasks/{task_id}/artifacts*` endpoints.

## Browser Policy

- Attach to existing dedicated browser (`CHROME_CDP_URL`).
- Manual login and verification are required outside automation.
- If browser session is unavailable, return `needs_manual_intervention`.
