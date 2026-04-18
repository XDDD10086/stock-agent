# AGENTS

## Mission

Build a local orchestrator that integrates GPT, Gemini, and ValueCell web execution through a dedicated attached browser session.

## Non-Goals

- Do not rebuild ValueCell analysis engine locally.
- Do not use browser automation as the planner/reviewer/finalizer.
- Do not run concurrent ValueCell tasks in one browser session.

## System Rules

1. User input can be free-form, execution internals must be structured.
2. Browser execution mode must be `attach_existing`.
3. Failure policy must be `manual_intervention` for browser/session issues.
4. Persist artifacts for every stage:
   - `plan_v1`
   - `review_v1`
   - `execution_pack`
   - `final_result`
5. Keep `.env` local only; never commit secrets.

## Runtime Guardrails

- `POST /tasks/{task_id}/run` is single-run guarded.
- Concurrent run requests must return `409 runner is busy`.
- ValueCell entry URL is `VALUECELL_CHAT_URL`.
