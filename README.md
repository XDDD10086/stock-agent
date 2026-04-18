# stock-agent

Local orchestration MVP for:

- GPT planner/finalizer contracts
- Gemini reviewer contract
- ValueCell execution via dedicated attached browser session
- Task and artifact persistence in SQLite
- Cron schedule API baseline
- Streamlit control panel

## Current Status

- Core task APIs: ready
- Run/result orchestration flow: ready (synchronous MVP)
- ValueCell runner: live attach validated against dedicated browser session
- Schedule APIs: ready, APScheduler live cron validation completed
- Streamlit MVP panel: ready
- Artifact inspection APIs: ready
- Parser table extraction: ready (markdown table -> structured rows)
- Parser bilingual extraction: ready (English + Chinese summary/risk/highlights)
- Observability artifacts: ready (`runner_diagnostics` + `orchestration_metrics`)
- LLM mode:
  - deterministic default (`USE_LIVE_LLM=false`)
  - live providers available (`USE_LIVE_LLM=true`)

## Quick Start

1. Create env files:
   - `.env` for local secrets
   - `.env.example` for template sharing
2. Install deps:
   - `pip install -r requirements.txt`
   - optional: `pip install -r requirements.optional.txt`
3. Start dedicated browser:
   - `./scripts/start_valuecell_browser.sh`
4. Verify CDP:
   - `./scripts/check_cdp_connection.sh`
5. Start API:
   - `./scripts/run_api.sh`
6. Start UI:
   - `./scripts/run_ui.sh`

UI sections:

- `Task Studio`
- `Schedule Desk`
- `Monitor`

## Tests

```bash
pytest -q
```

## MVP Smoke Check

When API is running and dedicated browser is logged in:

```bash
./scripts/smoke_mvp.sh
```

Useful options:

- `./scripts/smoke_mvp.sh --skip-schedule-check`
- `./scripts/smoke_mvp.sh --allow-manual-intervention`

## Key API Endpoints

- `POST /tasks`
- `POST /tasks/{task_id}/run`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/result`
- `GET /tasks/{task_id}/artifacts`
- `GET /tasks/{task_id}/artifacts/{artifact_type}`
- `POST /schedules`
- `GET /schedules`
- `POST /schedules/{id}/pause`
- `POST /schedules/{id}/resume`
- `DELETE /schedules/{id}`
