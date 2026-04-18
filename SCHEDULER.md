# SCHEDULER

## Goals

- Provide cron schedule management API.
- Support optional runtime execution through APScheduler.
- Reuse existing task orchestration path for scheduled runs.

## Feature Flag

- `SCHEDULER_ENABLED=true`: enable APScheduler runtime syncing.
- `SCHEDULER_ENABLED=false`: schedule records persist in DB only.

## API Surface

- `POST /schedules`
- `GET /schedules`
- `POST /schedules/{id}/pause`
- `POST /schedules/{id}/resume`
- `DELETE /schedules/{id}`

## Runtime Behavior

When runtime is enabled:

1. Creating a schedule registers/upserts a cron job.
2. Pausing/resuming updates both DB state and scheduler job state.
3. Deleting removes both DB record and scheduler job.
4. Triggered job creates a task and runs it through `ExecutionService`.

## Current Limitation

- Live cron validation still depends on available dedicated browser CDP session.
