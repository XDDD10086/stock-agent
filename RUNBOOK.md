# RUNBOOK

## 1. Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Optional:

```bash
pip install -r requirements.optional.txt
```

## 2. Start dedicated ValueCell browser session

```bash
./scripts/start_valuecell_browser.sh
```

In the browser:

1. Log in manually.
2. Complete any verification challenge.
3. Keep this browser window open.

## 3. Verify CDP availability

```bash
./scripts/check_cdp_connection.sh
```

Expected output: `CDP check: OK`

## 4. Run API

```bash
./scripts/run_api.sh
```

## 5. Run Streamlit console

```bash
./scripts/run_ui.sh
```

## 5.1 Run Discord bridge (optional)

```bash
./scripts/run_discord_bridge.sh
```

Channel behavior:

- Analyst channel(s): `/run` + unified analysis outputs.
- Scheduler channel(s): `/schedule create|list|cancel|pause|resume|run-once`.
- All final analysis outputs are posted to `DISCORD_RESULT_CHANNEL_ID`.

Schedule create interaction:

- Use only three fields in Discord:
  - `name`
  - `task_input`
  - `trigger` (natural language)
- The bridge parses `trigger` into scheduler payload (LLM-first, fallback parser if LLM is unavailable).

Streamlit Schedule Desk interaction:

- `Create Schedule` now also uses only three inputs:
  - `name`
  - `task description`
  - `trigger` (natural language)
- `trigger` is parsed with the same parser stack as Discord.
- Manage operations (`pause/resume/delete/run-once`) support schedule target by numeric `id` or unique `name`.

## 5.2 One-command stack manager (recommended)

```bash
./scripts/stack_ctl.sh start
./scripts/stack_ctl.sh status
./scripts/stack_ctl.sh stop
```

Optional:

- Open API docs + Streamlit automatically: `./scripts/stack_ctl.sh start --open`
- Tail combined logs: `./scripts/stack_ctl.sh logs`

Mac desktop launchers:

- Double-click `Start Stock Agent.command` to start services.
- Double-click `Stop Stock Agent.command` to stop services.
- Double-click `Stock Agent Status.command` to inspect state.

## 6. Test

```bash
. .venv/bin/activate
pytest -q
```

### 6.1 Full automation module sweep

```bash
.venv/bin/python -m pytest -q \
  tests/test_tasks_api.py \
  tests/test_schedules_api.py \
  tests/test_valuecell_runner_contract.py \
  tests/test_valuecell_parser.py \
  tests/test_valuecell_wait_logic.py \
  tests/test_execution_service_clients.py \
  tests/test_discord_bridge_policy.py \
  tests/test_discord_bridge_service.py \
  tests/test_discord_bridge_integration.py \
  tests/test_discord_bridge_formatter.py \
  tests/test_discord_bridge_runtime_utils.py \
  tests/test_discord_schedule_trigger_parser.py \
  tests/test_frontend_schedule_ui_helpers.py
```

### 6.2 Token exhausted mode (mock pass)

If ValueCell token is unavailable, set:

```bash
VALUECELL_MOCK_MODE=pass
```

With this flag enabled, task runs bypass ValueCell browser execution and return deterministic completed results for end-to-end workflow testing.

## 7. Live validation checklist (when browser is ready)

1. Start dedicated browser and complete manual login:
```bash
./scripts/start_valuecell_browser.sh
```
2. Confirm CDP is reachable:
```bash
./scripts/check_cdp_connection.sh
```
Expected: `CDP check: OK`
3. Run API:
```bash
./scripts/run_api.sh
```
4. In another terminal, trigger one task run:
```bash
curl -s -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"input":"daily portfolio risk scan"}'
```
Then:
```bash
curl -s -X POST http://127.0.0.1:8000/tasks/<TASK_ID>/run
```
5. Verify artifacts include `runner_diagnostics` and `final_result`:
```bash
curl -s http://127.0.0.1:8000/tasks/<TASK_ID>/artifacts
```
6. Validate one scheduler run:
```bash
curl -s -X POST http://127.0.0.1:8000/schedules \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke","task_input":"daily portfolio risk scan","cron":"*/10 * * * *"}'
```
7. Capture evidence for milestone logs:
- CDP check output
- task run response payload
- artifact list payload
- one scheduler-created task in `/tasks`

## 8. One-command MVP smoke

Prerequisites:

1. Dedicated browser is running and logged in.
2. API server is running (`./scripts/run_api.sh`).

Command:

```bash
./scripts/smoke_mvp.sh
```

Expected tail output:

- `[PASS] API health check passed`
- `[PASS] CDP endpoint reachable and debugger websocket exposed`
- `[PASS] Task run finished with status=completed`
- `[PASS] Scheduler created task: ...`
- `[PASS] Scheduled task finalized with status=completed`
- `[PASS] MVP smoke completed`
