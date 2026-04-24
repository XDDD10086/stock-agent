# SCHEDULER

## Goals

- Provide multi-trigger schedule management API.
- Support optional runtime execution through APScheduler.
- Reuse existing task orchestration path for scheduled runs.

## Feature Flag

- `SCHEDULER_ENABLED=true`: enable APScheduler runtime syncing.
- `SCHEDULER_ENABLED=false`: schedule records persist in DB only.

## API Surface

- `POST /schedules`
- `GET /schedules`
- `PATCH /schedules/{id}`
- `POST /schedules/{id}/pause`
- `POST /schedules/{id}/resume`
- `POST /schedules/{id}/run-once`
- `DELETE /schedules/{id}`

Supported trigger types:

- `cron` (`cron` required)
- `once` / `one-off` (`run_at_local` + `timezone` required)
- `daily` (`time_of_day` + `timezone` required)
- `weekly` (`time_of_day` + `days_of_week` + `timezone` required)
- `interval` (`interval_minutes` + `timezone` required)

## Runtime Behavior

When runtime is enabled:

1. Creating/updating a schedule registers/upserts the corresponding APScheduler trigger.
2. Pausing/resuming updates both DB state and scheduler job state.
3. Deleting removes both DB record and scheduler job.
4. Triggered job creates a task and runs it through `ExecutionService`.
5. Triggered runs persist `trigger_meta` artifact for downstream consumers (for example Discord bridge result routing).
6. `run-once` executes immediately without mutating the original schedule trigger definition.

## Current Limitation

- Live scheduler validation still depends on available dedicated browser CDP session.
