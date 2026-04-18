# LONG RUN EXECUTION BOARD

## Timebox

- Window: Rolling long-run (current block: 8h)
- Objective: Carry MVP from CDP-ready state to release-hardening completion.

## Milestone Queue

- [x] M0 Environment template + secret protection
- [x] M1 FastAPI + SQLite + task API baseline
- [x] M2 Planner/Reviewer/Finalizer service stubs + schema contracts
- [x] M3 ValueCell runner live attach validation
- [x] M4 Scheduler live cron verification
- [x] M5 Final stabilization and release hardening

## Parallelization Policy

- Max parallel tracks: 2
- Use parallel only for non-overlapping file ownership.
- Fall back to serial if shared files are touched in both tracks.

## Track Ownership (Current)

- Track A: `app/providers/valuecell_runner` + execution wiring (M3)
- Track B: `tests/` + runner integration checks (M3 quality)

## Current Checkpoint

- M3 checkpoint 2 complete: runnable execution flow + artifact persistence + run/result routes.
- M3 checkpoint 3 complete: parser normalization + artifact query APIs + single-run lock.
- M4 checkpoint 3 complete: APScheduler runtime wired with feature flag.
- M5 checkpoint 2 complete: runbook + browser helper scripts + CDP blocker identified.
- M5 checkpoint 3 complete: optional runtime dependencies installed and import-verified.
- M3 checkpoint 4 complete: live LLM toggle + provider implementations with deterministic default.
- M5 checkpoint 4 complete: governance docs baseline (AGENTS/ARCHITECTURE/TASKS/PROMPTS/SCHEDULER).
- M3 checkpoint 5 complete: provider JSON serialization contract + mocked live-provider tests.
- M5 checkpoint 5 complete: polished Streamlit console UX.
- M3 checkpoint 6 complete: ValueCell DOM completion heuristics + stable polling tests.
- M3 checkpoint 7 complete: runner diagnostics artifact persisted and API-test verified.
- M5 checkpoint 6 complete: live attach/cron validation checklist documented in runbook.
- M2 checkpoint 2 complete: prompt layer upgraded to v2 with risk grading and few-shot examples.
- M3 checkpoint 8 complete: live CDP attach validated with DOM-anchored assistant extraction.
- M4 checkpoint 4 complete: live cron smoke run validated and cleanup verified.
- M5 checkpoint 7 complete: observability artifacts added (orchestration metrics + runner timing history).
- M5 checkpoint 8 complete: parser quality hardened for bilingual output and UI-noise-heavy raw text.
- M5 checkpoint 9 complete: pytest warning hygiene cleanup (clean `31 passed` output).
- M5 checkpoint 10 complete: MVP handoff automation scripts + one-command smoke validation.
- Next focus: optional post-MVP refinements (async worker model, richer parser schema, CI matrix).

## Active Long Task Plan

1. [x] Harden ValueCell completion heuristics and add deterministic wait-loop tests.
2. [x] Add richer runner diagnostics artifact for failed runs (without exposing secrets).
3. [x] Execute live CDP attach validation after dedicated browser is started with remote debugging.
4. [x] Execute one end-to-end scheduler cron run with attached browser and capture evidence.
5. [x] Add orchestration telemetry artifacts and parser hardening for M5 quality.
6. [x] Remove noisy third-party warning output in local test runs.
7. [x] Add one-command startup/smoke scripts for MVP handoff.

## Definition of Progress

- Every completed milestone must update:
  - `docs/DECISIONS.md` (if new decision made)
  - `docs/MILESTONES.md` (status + evidence)
- Each milestone needs at least one verification command with captured result summary.
