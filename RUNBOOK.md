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

## 6. Test

```bash
. .venv/bin/activate
pytest -q
```

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
