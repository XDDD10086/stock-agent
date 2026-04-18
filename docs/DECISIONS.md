# DECISIONS

## D-001 Secret and Environment File Policy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Real secrets must live only in `.env` on local machines.
- `.env.example` is the only environment template tracked in version control.
- `.gitignore` must ignore `.env` and `.env.*`, while allowing `.env.example`.

### Rationale

- Prevent accidental secret leakage to remote repositories.
- Keep onboarding simple with a complete environment template.
- Ensure future environment variables are documented in one canonical template.

### Consequences

- Every new environment key must be added to both `.env` (local) and `.env.example` (template).
- If `.env` is ever accidentally tracked, remove it with `git rm --cached .env` and commit the fix.

## D-002 Python 3.14 Dependency Strategy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Keep `requirements.txt` focused on core backend dependencies for M1.
- Move `openai/google-genai/playwright/streamlit` to `requirements.optional.txt` for later milestones.

### Rationale

- The current local interpreter is Python 3.14.
- Some pinned packages failed to build under Python 3.14 (`greenlet`, older `pydantic-core`).
- Splitting dependencies unblocks backend milestone delivery without blocking on runtime matrix work.

### Consequences

- M1 can proceed with tests and API implementation immediately.
- M2+ must validate optional dependency compatibility before installing browser/UI/tooling stack.

## D-003 Dedicated Browser Execution Policy

- Date: 2026-04-17
- Status: Accepted

### Decision

- ValueCell automation must run in `attach_existing` mode against a dedicated real browser session.
- Entry URL is fixed to `VALUECELL_CHAT_URL` (`https://valuecell.cn/zh/chat` in current env template).
- Failure policy is `manual_intervention` for disconnected/unverified sessions.

### Rationale

- Dedicated real browser sessions are more stable under anti-bot checks than ephemeral test browsers.
- Manual login once + long-lived session reduces verification and captcha friction.
- Explicit policy avoids ambiguous retry behavior during failure cases.

### Consequences

- Runner preflight validates `attach_existing` and `manual_intervention` constraints.
- Full browser automation steps (CDP attach + page actions + artifact capture) remain M3 follow-up work.

## D-004 Synchronous Run Endpoint for MVP

- Date: 2026-04-17
- Status: Accepted

### Decision

- Implement `POST /tasks/{task_id}/run` as a synchronous request in MVP.
- Persist every stage artifact (`plan_v1`, `review_v1`, `execution_pack`, `final_result`) into `task_artifacts`.
- Expose `GET /tasks/{task_id}/result` to fetch normalized final output.

### Rationale

- Synchronous execution keeps orchestration behavior inspectable during early milestone work.
- Artifact persistence creates replay/debug evidence before queue/worker infrastructure exists.
- Route-level run/result endpoints align with blueprint contract and accelerate frontend integration.

### Consequences

- Long-running browser runs can hold request threads in MVP.
- Queue-based async execution can replace this later without changing artifact schema.

## D-005 Single-Runner Concurrency Guard

- Date: 2026-04-17
- Status: Accepted

### Decision

- Guard `POST /tasks/{task_id}/run` with a non-blocking execution lock.
- If a run is already active, return HTTP `409` with detail `runner is busy`.

### Rationale

- The MVP browser execution model uses one dedicated attached browser session.
- Concurrent run requests can corrupt page interaction state and artifacts.
- Explicit conflict responses are safer than queuing hidden in API layer for now.

### Consequences

- API clients can implement explicit retry/backoff on 409.
- Future queue execution can reuse this policy or replace it behind worker dispatch.

## D-006 Live LLM Toggle with Safe Default

- Date: 2026-04-17
- Status: Accepted

### Decision

- Add `USE_LIVE_LLM` environment switch.
- Default is `false`, which keeps deterministic planner/reviewer/finalizer behavior.
- When `true`, orchestration uses:
  - `OpenAIClient.for_planner()`
  - `GeminiClient.for_reviewer()`
  - `OpenAIClient.for_finalizer()`

### Rationale

- Keeps local tests deterministic and network-independent.
- Allows immediate transition to real model calls without changing route/service interfaces.

### Consequences

- `.env.example` now includes `USE_LIVE_LLM=false`.
- Live mode requires valid `OPENAI_API_KEY` and `GEMINI_API_KEY`.

## D-007 Provider JSON Serialization Contract

- Date: 2026-04-17
- Status: Accepted

### Decision

- Live provider request payloads must serialize structured input using JSON (`json.dumps`), not Python `dict` string formatting.

### Rationale

- Python dict repr uses single quotes and is not valid JSON.
- JSON serialization yields stable, model-friendly structure for planner/reviewer/finalizer handoff.

### Consequences

- OpenAI finalizer input and Gemini reviewer input now carry explicit JSON strings.
- Added mocked integration tests to enforce this contract.

## D-008 ValueCell Completion Heuristic Policy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Browser completion detection uses a two-stage heuristic:
  - Ignore loading/typing/thinking text signals.
  - Accept completion only after a meaningful assistant response is observed in two stable polls.

### Rationale

- ValueCell pages can render assistant blocks before final content is complete.
- Single-shot selector waits create false positives and premature artifact capture.
- Stable polling reduces flaky completion outcomes without requiring site-specific private APIs.

### Consequences

- `PlaywrightCdpAdapter.wait_until_completed` now polls message text with timeout bounds.
- Added unit tests for:
  - loading-state keyword detection
  - meaningful response threshold
  - stable-poll completion and timeout behavior

## D-009 Runner Diagnostics Artifact Policy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Persist a dedicated `runner_diagnostics` artifact for every task run, regardless of success/failure.

### Rationale

- Manual intervention workflows need quick visibility into failed step, timeout, and artifact paths.
- Keeping diagnostics separate from `final_result` preserves user-facing result clarity while improving troubleshooting speed.

### Consequences

- `ExecutionService.run_task` now writes `runner_diagnostics` before final result normalization.
- Artifact inspection endpoint can fetch diagnostics directly via:
  - `GET /tasks/{task_id}/artifacts/runner_diagnostics`

## D-010 Prompt Layer v2 Strategy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Upgrade planner/reviewer/finalizer system prompts to v2 with:
  - strict schema-oriented output constraints
  - explicit Green/Yellow/Red risk-rating framing
  - few-shot JSON examples for output stability

### Rationale

- v1 prompts were minimal and prone to under-specified outputs in live mode.
- Structured constraints plus examples improve determinism for cross-model orchestration (OpenAI + Gemini).
- Risk-rating consistency is critical for downstream normalization and operator review.

### Consequences

- Prompt files under `app/prompts/` now contain operational guardrails and examples.
- `PROMPTS.md` now documents v2 behavior expectations.

## D-011 ValueCell Chat DOM Anchoring Strategy

- Date: 2026-04-17
- Status: Accepted

### Decision

- For completion detection, prefer ValueCell's `main.main-chat-area > section` structure over generic `.assistant/.message` selectors.
- Extract only assistant content that appears after the latest user turn (`ml-auto` section), then evaluate completion.

### Rationale

- Live page uses site-specific section layout and does not expose reliable generic assistant classes.
- Generic selectors caused missed responses and timeout risk.
- Anchoring after the latest user turn avoids false positives from historical conversation content.

### Consequences

- `wait_until_completed` now waits on the chat container and polls DOM-anchored assistant sections.
- Live attach run moved from `submit_prompt` failure/timeout risk to stable completion in dedicated browser session.

## D-012 Orchestration Metrics Artifact Strategy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Persist `orchestration_metrics` for every run with per-stage and total execution durations.
- Extend `runner_diagnostics` with runner-level timing fields and step history.

### Rationale

- M5 needs production-grade visibility on where time is spent (plan/review/finalize/runner).
- Existing diagnostics focused on failures but lacked consistent stage timing telemetry.

### Consequences

- Task artifacts now include:
  - `orchestration_metrics`
  - richer `runner_diagnostics` (`started_at_utc`, `ended_at_utc`, `duration_seconds`, `step_history`)
- API consumers can inspect both outcome and stage-level performance without extra instrumentation.

## D-013 Bilingual Parser Hardening Strategy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Expand parser to support both English and Chinese sections for summary/highlights/risk rating.
- Add preprocessing to strip common ValueCell UI chrome noise before extraction.

### Rationale

- Live raw artifacts include mixed-language content and repeated UI text that degrades extraction quality.
- v1 parser relied on English-only headings and missed high-signal Chinese outputs.

### Consequences

- Parser now handles:
  - `Executive Summary` / `执行摘要`
  - `Highlights` / `核心风险点` / `关键要点`
  - risk labels in English and Chinese (e.g., `黄灯`, `红色`)
- Parsed outputs are less polluted by navigation/sidebar/system lines captured from full-page text.

## D-014 Test Warning Hygiene Strategy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Suppress known third-party deprecation warning from `google.genai.types` in pytest configuration.

### Rationale

- The warning originates from upstream dependency internals on Python 3.14 and does not indicate project code regression.
- Keeping test output warning-free improves CI readability and avoids alert fatigue.

### Consequences

- `pytest -q` now reports clean pass output (`31 passed`) without the recurring dependency deprecation warning.
- If upstream package behavior changes, this filter can be removed in a later dependency refresh.

## D-015 MVP Handoff Automation Strategy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Add operational wrapper scripts for API/UI startup and end-to-end MVP smoke validation:
  - `scripts/run_api.sh`
  - `scripts/run_ui.sh`
  - `scripts/smoke_mvp.sh`
  - `scripts/smoke_mvp.py`

### Rationale

- Manual multi-step startup/check flows are error-prone at handoff time.
- A deterministic smoke command provides a repeatable acceptance gate for “MVP usable now”.

### Consequences

- README and runbook now use wrapper scripts as primary path.
- MVP acceptance can be executed with one command once browser + API are up:
  - `./scripts/smoke_mvp.sh`

## D-016 Prompt Gate Revision Policy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Frontend input is treated as user intent only; the ValueCell submission prompt must come from planner/reviewer/finalizer chain output.
- When reviewer output is `approved=false`, orchestration performs one revision pass before finalization.
- Persist a `prompt_chain` artifact for every run:
  - `user_intent`
  - `plan`
  - `review`
  - `revised_plan` (nullable)
  - `final_prompt`
  - `review_gate_status` (`direct_pass` or `revised_once`)

### Rationale

- Prevent direct pass-through prompting from UI intent text.
- Make review-gated prompt evolution auditable for operations and debugging.
- Keep behavior deterministic and bounded by single-pass revision.

### Consequences

- Final ValueCell prompt is always orchestration-generated.
- `FinalResult` now exposes `prompt_chain_status`.

## D-017 ValueCell Raw Response Roundtrip Policy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Runner captures the latest assistant message as primary raw response source.
- If latest assistant extraction is empty, fallback to full-page text capture.
- Persist `valuecell_raw_response` artifact and return raw response directly in `FinalResult`.

### Rationale

- Operators need the exact ValueCell answer in the same task context without file-system lookup.
- Assistant-first extraction reduces UI noise compared with body-level scraping.

### Consequences

- `FinalResult` now includes `valuecell_raw_response`.
- Frontend can render structured + raw panels in one workflow view.

## D-018 Unified Schedule Trigger Matrix Policy

- Date: 2026-04-17
- Status: Accepted

### Decision

- Scheduler supports four trigger types:
  - `cron`
  - `once`
  - `daily`
  - `weekly`
- Add `POST /schedules/{id}/run-once` for immediate manual execution.
- Add `PATCH /schedules/{id}` for trigger updates without delete/recreate.
- One-time schedule semantics:
  - `run_at_local + timezone` are converted to `run_at_utc` for persistence.
  - record is retained after execution for audit/reuse.
  - rerun path is `run-once` or update/re-enable, not automatic repetition.

### Rationale

- Cron-only API could not express one-off and template schedules cleanly.
- Preserving one-time records supports traceability and reusability.

### Consequences

- Schedule DB schema now includes `run_at_utc`, `time_of_day`, `days_of_week`.
- App startup applies idempotent SQLite compat migrations for new columns.

## D-019 Runtime LLM Mode Transparency and Completion Strictness

- Date: 2026-04-18
- Status: Accepted

### Decision

- Surface runtime LLM mode (`live` vs `deterministic`) in task outputs and prompt-chain artifacts.
- Tighten ValueCell completion detection to avoid early capture of "intermediate reasoning/progress" text.
- Rank multiple assistant candidates and prefer higher-quality completion-like response blocks.

### Rationale

- Operators must be able to confirm whether runs used real OpenAI/Gemini or deterministic fallback.
- Early completion false positives caused incomplete raw responses and poor final parsing quality.

### Consequences

- `FinalResult` now includes `llm_mode`.
- `wait_until_completed` requires richer final-response signals and additional stability polls.
- Intermediate markers like `正在执行任务/思考过程/构建分析策略` are excluded from final capture.
