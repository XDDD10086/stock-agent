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
- [x] M6 Prompt gate hardening + ValueCell roundtrip + scheduler matrix
- [x] M7 Committee report chain + trigger matrix expansion
- [x] M8 Discord dual-channel control console (analyst/scheduler split)
- [x] M9 Documentation + deployment/ops hardening + release hygiene

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
- M6 checkpoint 1 complete: review-gated prompt revision (`revised_once`) + prompt-chain artifact audit trail.
- M6 checkpoint 2 complete: ValueCell raw assistant response roundtrip to API + frontend dual-panel rendering.
- M6 checkpoint 3 complete: scheduler trigger matrix (`once/cron/daily/weekly`) + patch/run-once APIs + sqlite compat migration.
- M6 checkpoint 4 complete: llm-mode visibility + stricter ValueCell completion heuristics to prevent premature capture.
- M6 checkpoint 5 complete: live-provider failure fallback to deterministic with explicit diagnostics (no user-facing 500).
- M6 checkpoint 6 complete: frontend long-run timeout + send-ready completion gate to avoid premature scrape.
- M6 checkpoint 7 complete: completion detection now accepts reply action-bar (`复制/保存/详情`) and disabled paper-plane visibility.
- M6 checkpoint 8 complete: mixed final text with `思考过程` labels no longer blocks completion when final markers are present.
- M7 checkpoint 1 complete: post-ValueCell committee chain (GPT draft -> Gemini review -> GPT finalize) with fallback-safe output.
- M7 checkpoint 2 complete: committee output upgraded to report-mode (`committee_report_json` + markdown rendering) with stronger finalizer prompt constraints.
- M7 checkpoint 3 complete: scheduler trigger matrix expanded with `one-off` and `interval(interval_minutes)` plus API test coverage.
- M8 checkpoint 1 complete: Discord bridge process scaffolded with slash command routing and channel/role authorization policy.
- M8 checkpoint 2 complete: analyst-result unification delivered for manual `/run` and scheduled runs (poll + dedupe state file).
- M8 checkpoint 3 complete: schedule trigger metadata (`trigger_meta`) persisted for `run-once` and scheduler callbacks.
- M8 checkpoint 4 complete: Discord bridge unit/integration coverage added with API-backed fake-adapter validation.
- M9 checkpoint 1 complete: full README rewrite with architecture/stack/deploy/features/Discord routing coverage.
- M9 checkpoint 2 complete: added `docs/DEPLOYMENT.md` and `docs/FRONTEND_BACKEND.md` for operations and integration handoff.
- M9 checkpoint 3 complete: final regression and release hygiene checks (`92 passed`, sensitive-pattern scan clean).
- Next focus: optional post-MVP refinements (async worker model, richer parser schema, CI matrix).

## Active Long Task Plan

1. [x] Harden ValueCell completion heuristics and add deterministic wait-loop tests.
2. [x] Add richer runner diagnostics artifact for failed runs (without exposing secrets).
3. [x] Execute live CDP attach validation after dedicated browser is started with remote debugging.
4. [x] Execute one end-to-end scheduler cron run with attached browser and capture evidence.
5. [x] Add orchestration telemetry artifacts and parser hardening for M5 quality.
6. [x] Remove noisy third-party warning output in local test runs.
7. [x] Add one-command startup/smoke scripts for MVP handoff.
8. [x] Implement M6 pipeline hardening and scheduler expansion with full regression tests.
9. [x] Fix post-acceptance issues: enforce visible LLM mode and block intermediate-response false positives.
10. [x] Add runtime fallback guard for live-LLM quota/provider errors.
11. [x] Align long-running UX timeout and ValueCell send-ready completion signal.
12. [x] Add completion action-bar signal and visible-send fallback for ValueCell finished-state detection.
13. [x] Allow completion markers to override noisy thinking labels in final response blocks.
14. [x] Add committee summarization chain and committee-first frontend presentation.
15. [x] Upgrade committee from summary-actions to report-grade output schema and UI rendering.
16. [x] Add scheduler `one-off` and `interval` triggers with persistence/scheduler wiring/tests.
17. [x] Add Discord dual-channel bridge with command split, unified analyst result sink, and delivery dedupe.

## Definition of Progress

- Every completed milestone must update:
  - `docs/DECISIONS.md` (if new decision made)
  - `docs/MILESTONES.md` (status + evidence)
- Each milestone needs at least one verification command with captured result summary.
