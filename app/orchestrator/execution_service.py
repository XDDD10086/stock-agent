from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from time import perf_counter
from typing import Callable

from app.orchestrator.committee_service import CommitteeDraftService
from app.orchestrator.committee_service import CommitteeFinalizeService
from app.orchestrator.committee_service import CommitteeReviewService
from app.orchestrator.finalize_service import FinalizeService
from app.orchestrator.planner_service import PlannerService
from app.orchestrator.review_service import ReviewService
from app.orchestrator.task_service import TaskService
from app.parsers.valuecell_parser import parse_valuecell_text
from app.providers.gemini_client import GeminiClient
from app.providers.openai_client import OpenAIClient
from app.providers.valuecell_runner import BrowserAdapter, RunnerConfig, ValueCellRunner
from app.schemas.plan import PlanV1
from app.schemas.result import FinalResult

_EXECUTION_LOCK = Lock()


class DeterministicPlannerClient:
    def plan(self, task_input: str) -> dict:
        intent = task_input.strip()
        return {
            "objective": f"围绕用户意图“{intent}”，生成可执行的投资研究分析并输出结构化结论。",
            "constraints": [
                "run with dedicated attached browser",
                "research only, no trade execution",
                "output must include summary table and risk rating",
            ],
            "required_outputs": ["summary", "table", "risk_rating"],
            "steps": [
                "clarify objective and assumptions",
                "build a structured valuecell prompt",
                "request evidence-backed factors and risks",
                "normalize output into summary table and risk rating",
            ],
            "risk_flags": ["data_freshness", "missing_time_horizon"],
            "needs_review": True,
        }


class DeterministicReviewerClient:
    def review(self, plan: dict) -> dict:
        return {
            "approved": True,
            "missing_items": [],
            "ambiguities": [],
            "risk_flags": [],
            "suggested_changes": [],
        }


class DeterministicFinalizerClient:
    def finalize(self, plan: dict, review: dict) -> dict:
        prompt = (
            f"{plan['objective']}\n\n"
            "请按以下结构输出：\n"
            "1) 执行摘要（3-5条要点）\n"
            "2) 风险与机会表格（factor/signal/impact/confidence）\n"
            "3) 最终风险评级（Green/Yellow/Red）及简要依据\n"
            "4) 未来5个交易日重点观察项（最多3条）\n"
            "要求：避免空话，给出可解释依据，若信息不足请明确说明不确定性。"
        )
        return {
            "target": "valuecell_web",
            "valuecell_prompt": prompt,
            "expected_sections": ["summary", "table", "risk_rating"],
            "browser_steps": [
                {"action": "open_chat"},
                {"action": "fill_prompt", "content": prompt},
                {"action": "submit"},
                {"action": "wait_until_completed"},
            ],
            "timeout_seconds": 900,
        }


class DeterministicCommitteeDrafterClient:
    def committee_draft(self, context: dict) -> dict:
        parsed = context.get("parsed_result", {})
        summary = str(parsed.get("summary") or "").strip()
        highlights = [str(item).strip() for item in parsed.get("highlights", []) if str(item).strip()]
        risk_rating = str(parsed.get("risk_rating", "unknown")).strip().lower()

        if not summary:
            summary = "当前信息显示主要风险与机会并存，建议以分步验证和风险控制为主。"

        actions: list[dict] = []
        for item in highlights[:4]:
            actions.append(
                {
                    "action": f"优先检查：{item}",
                    "reason": "该项来自 ValueCell 的关键信号，需先确认其持续性和可验证性。",
                }
            )
        if not actions:
            actions = [
                {
                    "action": "先缩小观察范围到未来 5 个交易日的关键催化事件",
                    "reason": "先聚焦短期可验证因素，可以降低决策噪声。",
                },
                {
                    "action": "为仓位与回撤设置明确阈值，再决定是否调整风险暴露",
                    "reason": "有阈值的策略更易执行，也能避免情绪化操作。",
                },
            ]

        risks = [f"当前综合风险评级：{risk_rating}"] if risk_rating and risk_rating != "unknown" else []
        return {
            "summary": summary,
            "actions": actions,
            "risks": risks,
        }


class DeterministicCommitteeReviewerClient:
    def committee_review(self, draft: dict, context: dict) -> dict:
        actions = draft.get("actions") or []
        if len(actions) < 2:
            return {
                "approved": False,
                "issues": ["action count is too low for a practical strategy summary"],
                "suggested_changes": ["add at least two actionable steps with explicit reasons"],
                "safety_notes": ["do not present directional certainty when evidence is sparse"],
            }
        return {
            "approved": True,
            "issues": [],
            "suggested_changes": [],
            "safety_notes": ["treat this as research support and validate with your own risk limits"],
        }


class DeterministicCommitteeFinalizerClient:
    def committee_finalize(self, draft: dict, review: dict, context: dict) -> dict:
        summary = str(draft.get("summary") or "").strip()
        actions = list(draft.get("actions") or [])
        parsed = context.get("parsed_result", {})
        risk_rating = str(parsed.get("risk_rating", "unknown")).strip().lower()

        if review.get("suggested_changes"):
            suggestion = str(review["suggested_changes"][0]).strip()
            actions.append(
                {
                    "action": f"补充校验：{suggestion}",
                    "reason": "审查环节建议补充该项，以提升策略完整性和可执行性。",
                }
            )

        if risk_rating and risk_rating != "unknown":
            suffix = f"当前风险评级为 {risk_rating}，建议小步执行并持续复盘。"
            summary = f"{summary} {suffix}".strip()

        deduped_actions: list[dict] = []
        seen: set[str] = set()
        for item in actions:
            action = str(item.get("action", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if not action or not reason:
                continue
            key = f"{action}|{reason}"
            if key in seen:
                continue
            seen.add(key)
            deduped_actions.append({"action": action, "reason": reason})

        if not deduped_actions:
            deduped_actions.append(
                {
                    "action": "先保持观察并等待下一批可验证数据",
                    "reason": "当前可执行证据不足，贸然调整可能放大噪声风险。",
                }
            )

        return {
            "committee_summary": summary or "已完成二次提炼，建议按风险可控原则分步执行。",
            "committee_actions": deduped_actions[:5],
        }


class ExecutionService:
    def __init__(
        self,
        task_service: TaskService,
        runner: ValueCellRunner,
        adapter_factory: Callable[[], BrowserAdapter] | None = None,
    ) -> None:
        self._task_service = task_service
        self._runner = runner
        self._adapter_factory = adapter_factory

    def run_task(self, task_id: str, task_input: str) -> FinalResult:
        started_at = datetime.now(UTC)
        run_clock_start = perf_counter()
        self._task_service.update_status(task_id, "running")
        llm_mode = resolve_llm_mode_from_env()
        planner_client, reviewer_client, finalizer_client = build_llm_clients_from_env()
        llm_fallback_reason: str | None = None

        try:
            (
                plan,
                review,
                execution_pack,
                plan_seconds,
                review_seconds,
                finalize_seconds,
                review_gate_status,
                revised_plan,
            ) = self._run_llm_chain(
                task_id=task_id,
                task_input=task_input,
                planner_client=planner_client,
                reviewer_client=reviewer_client,
                finalizer_client=finalizer_client,
            )
        except Exception as exc:
            if llm_mode != "live":
                raise
            llm_fallback_reason = f"{type(exc).__name__}: {exc}"
            self._task_service.save_artifact(
                task_id,
                "llm_live_error",
                {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "captured_at_utc": datetime.now(UTC).isoformat(),
                },
            )
            llm_mode = "live_fallback_deterministic"
            (
                plan,
                review,
                execution_pack,
                plan_seconds,
                review_seconds,
                finalize_seconds,
                review_gate_status,
                revised_plan,
            ) = self._run_llm_chain(
                task_id=task_id,
                task_input=task_input,
                planner_client=DeterministicPlannerClient(),
                reviewer_client=DeterministicReviewerClient(),
                finalizer_client=DeterministicFinalizerClient(),
            )

        self._task_service.save_artifact(
            task_id,
            "prompt_chain",
            {
                "user_intent": task_input,
                "plan": plan.model_dump(),
                "review": review.model_dump(),
                "revised_plan": revised_plan,
                "final_prompt": execution_pack.valuecell_prompt,
                "review_gate_status": review_gate_status,
                "llm_mode": llm_mode,
                "llm_fallback_reason": llm_fallback_reason,
            },
        )

        adapter = self._adapter_factory() if self._adapter_factory else None
        stage_start = perf_counter()
        outcome = self._runner.execute(task_id=task_id, execution_pack=execution_pack, adapter=adapter)
        runner_seconds = round(perf_counter() - stage_start, 3)
        self._task_service.save_artifact(
            task_id,
            "runner_diagnostics",
            _build_runner_diagnostics(outcome, execution_pack.timeout_seconds),
        )
        final_result = _normalize_outcome(
            outcome,
            prompt_chain_status=review_gate_status,
            llm_mode=llm_mode,
            llm_fallback_reason=llm_fallback_reason,
        )
        self._task_service.save_artifact(
            task_id,
            "valuecell_raw_response",
            {
                "text": final_result.valuecell_raw_response or "",
                "raw_text_path": outcome.raw_text_path,
            },
        )
        committee_chain, committee_result_payload = self._run_committee_chain(
            task_id=task_id,
            task_input=task_input,
            final_result=final_result,
            prompt_chain_status=review_gate_status,
            llm_mode=llm_mode,
        )
        self._task_service.save_artifact(task_id, "committee_chain", committee_chain)
        self._task_service.save_artifact(task_id, "committee_result", committee_result_payload)

        self._task_service.save_artifact(task_id, "final_result", final_result.model_dump())
        ended_at = datetime.now(UTC)
        self._task_service.save_artifact(
            task_id,
            "orchestration_metrics",
            _build_orchestration_metrics(
                task_id=task_id,
                started_at=started_at,
                ended_at=ended_at,
                plan_seconds=plan_seconds,
                review_seconds=review_seconds,
                finalize_seconds=finalize_seconds,
                runner_seconds=runner_seconds,
                total_seconds=round(perf_counter() - run_clock_start, 3),
            ),
        )
        self._task_service.update_status(task_id, final_result.status)
        return final_result

    def _run_committee_chain(
        self,
        *,
        task_id: str,
        task_input: str,
        final_result: FinalResult,
        prompt_chain_status: str,
        llm_mode: str,
    ) -> tuple[dict, dict]:
        context = {
            "task_input": task_input,
            "task_id": task_id,
            "prompt_chain_status": prompt_chain_status,
            "parsed_result": {
                "summary": final_result.summary,
                "highlights": final_result.highlights,
                "table": final_result.table,
                "risk_rating": final_result.risk_rating,
            },
            "valuecell_raw_response": final_result.valuecell_raw_response or "",
        }

        if final_result.status != "completed":
            final_result.committee_status = "skipped_not_completed"
            final_result.committee_summary = None
            final_result.committee_actions = []
            final_result.committee_fallback_reason = None
            skipped_payload = {
                "status": "skipped_not_completed",
                "reason": f"task status is {final_result.status}",
                "captured_at_utc": datetime.now(UTC).isoformat(),
            }
            return skipped_payload, {
                "committee_status": final_result.committee_status,
                "committee_summary": final_result.committee_summary,
                "committee_actions": final_result.committee_actions,
                "committee_fallback_reason": final_result.committee_fallback_reason,
            }

        drafter, reviewer, finalizer = build_committee_clients_from_env(llm_mode=llm_mode)
        try:
            draft_model = CommitteeDraftService(drafter).build_draft(context)
            review_model = CommitteeReviewService(reviewer).review_draft(draft_model, context)
            final_model = CommitteeFinalizeService(finalizer).finalize(draft_model, review_model, context)

            final_result.committee_status = "completed"
            final_result.committee_summary = final_model.committee_summary
            final_result.committee_actions = [item.model_dump() for item in final_model.committee_actions]
            final_result.committee_fallback_reason = None

            chain_payload = {
                "status": "completed",
                "context": context,
                "draft": draft_model.model_dump(),
                "review": review_model.model_dump(),
                "final": final_model.model_dump(),
                "captured_at_utc": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            final_result.committee_status = "fallback"
            final_result.committee_summary = None
            final_result.committee_actions = []
            final_result.committee_fallback_reason = f"{type(exc).__name__}: {exc}"

            chain_payload = {
                "status": "fallback",
                "context": context,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "captured_at_utc": datetime.now(UTC).isoformat(),
            }

        result_payload = {
            "committee_status": final_result.committee_status,
            "committee_summary": final_result.committee_summary,
            "committee_actions": final_result.committee_actions,
            "committee_fallback_reason": final_result.committee_fallback_reason,
            "captured_at_utc": datetime.now(UTC).isoformat(),
        }
        return chain_payload, result_payload

    def _run_llm_chain(
        self,
        *,
        task_id: str,
        task_input: str,
        planner_client,
        reviewer_client,
        finalizer_client,
    ):
        stage_start = perf_counter()
        plan = PlannerService(client=planner_client).generate_plan(task_input)
        plan_seconds = round(perf_counter() - stage_start, 3)
        self._task_service.save_artifact(task_id, "plan_v1", plan.model_dump())

        stage_start = perf_counter()
        review = ReviewService(client=reviewer_client).review_plan(plan)
        review_seconds = round(perf_counter() - stage_start, 3)
        self._task_service.save_artifact(task_id, "review_v1", review.model_dump())

        review_gate_status = "direct_pass"
        revised_plan = None
        active_plan = plan
        if not review.approved:
            active_plan = _revise_plan_once(plan, review)
            revised_plan = active_plan.model_dump()
            review_gate_status = "revised_once"

        stage_start = perf_counter()
        execution_pack = FinalizeService(client=finalizer_client).build_execution_pack(active_plan, review)
        finalize_seconds = round(perf_counter() - stage_start, 3)
        self._task_service.save_artifact(task_id, "execution_pack", execution_pack.model_dump())
        return (
            plan,
            review,
            execution_pack,
            plan_seconds,
            review_seconds,
            finalize_seconds,
            review_gate_status,
            revised_plan,
        )

    def get_result(self, task_id: str) -> FinalResult | None:
        payload = self._task_service.get_latest_artifact(task_id, "final_result")
        if payload is None:
            return None
        return FinalResult.model_validate(payload)


def try_acquire_execution_lock() -> bool:
    return _EXECUTION_LOCK.acquire(blocking=False)


def release_execution_lock() -> None:
    if _EXECUTION_LOCK.locked():
        _EXECUTION_LOCK.release()


def build_llm_clients_from_env():
    use_live = resolve_llm_mode_from_env() == "live"
    if use_live:
        return OpenAIClient.for_planner(), GeminiClient.for_reviewer(), OpenAIClient.for_finalizer()
    return DeterministicPlannerClient(), DeterministicReviewerClient(), DeterministicFinalizerClient()


def build_committee_clients_from_env(*, llm_mode: str):
    use_live = llm_mode == "live"
    if use_live:
        return (
            OpenAIClient.for_committee_drafter(),
            GeminiClient.for_committee_reviewer(),
            OpenAIClient.for_committee_finalizer(),
        )
    return (
        DeterministicCommitteeDrafterClient(),
        DeterministicCommitteeReviewerClient(),
        DeterministicCommitteeFinalizerClient(),
    )


def resolve_llm_mode_from_env() -> str:
    import os

    return "live" if os.getenv("USE_LIVE_LLM", "false").lower() == "true" else "deterministic"


def build_runner_config_from_env() -> RunnerConfig:
    import os

    return RunnerConfig(
        chat_url=os.getenv("VALUECELL_CHAT_URL", "https://valuecell.cn/zh/chat"),
        cdp_url=os.getenv("CHROME_CDP_URL", "http://127.0.0.1:9222"),
        execution_mode=os.getenv("BROWSER_EXECUTION_MODE", "attach_existing"),
        failure_policy=os.getenv("BROWSER_FAILURE_POLICY", "manual_intervention"),
        screenshots_dir=os.getenv("SCREENSHOTS_DIR", "./screenshots"),
        artifacts_dir=os.getenv("ARTIFACTS_DIR", "./artifacts"),
        poll_interval_seconds=int(os.getenv("VALUECELL_POLL_INTERVAL_SECONDS", "5")),
    )


def _build_runner_diagnostics(outcome, timeout_seconds: int) -> dict:
    return {
        "task_id": outcome.task_id,
        "status": outcome.status,
        "failed_step": outcome.failed_step,
        "error_message": outcome.error_message,
        "screenshot_path": outcome.screenshot_path,
        "raw_text_path": outcome.raw_text_path,
        "raw_response_chars": len(outcome.raw_response_text or ""),
        "timeout_seconds": timeout_seconds,
        "started_at_utc": outcome.started_at_utc,
        "ended_at_utc": outcome.ended_at_utc,
        "duration_seconds": outcome.duration_seconds,
        "step_history": outcome.step_history or [],
        "captured_at_utc": datetime.now(UTC).isoformat(),
    }


def _revise_plan_once(plan, review) -> PlanV1:
    constraints = list(plan.constraints)
    steps = list(plan.steps)

    for item in review.missing_items:
        note = f"review_required: {item}"
        if note not in constraints:
            constraints.append(note)

    for item in review.ambiguities:
        note = f"review_ambiguity: {item}"
        if note not in constraints:
            constraints.append(note)

    for item in review.suggested_changes:
        step = f"apply reviewer suggestion: {item}"
        if step not in steps:
            steps.append(step)

    revised_objective = plan.objective
    if review.suggested_changes or review.missing_items or review.ambiguities:
        revised_objective = f"{plan.objective} (review-adjusted)"

    merged_risks = list(dict.fromkeys([*plan.risk_flags, *review.risk_flags]))
    return PlanV1(
        objective=revised_objective,
        constraints=constraints,
        required_outputs=plan.required_outputs,
        steps=steps,
        risk_flags=merged_risks,
        needs_review=False,
    )


def _build_orchestration_metrics(
    *,
    task_id: str,
    started_at: datetime,
    ended_at: datetime,
    plan_seconds: float,
    review_seconds: float,
    finalize_seconds: float,
    runner_seconds: float,
    total_seconds: float,
) -> dict:
    return {
        "task_id": task_id,
        "started_at_utc": started_at.isoformat(),
        "ended_at_utc": ended_at.isoformat(),
        "plan_seconds": plan_seconds,
        "review_seconds": review_seconds,
        "finalize_seconds": finalize_seconds,
        "runner_seconds": runner_seconds,
        "total_seconds": total_seconds,
    }


def _normalize_outcome(outcome, *, prompt_chain_status: str, llm_mode: str, llm_fallback_reason: str | None) -> FinalResult:
    parsed = {"summary": "", "highlights": [], "risk_rating": "unknown", "table": []}
    raw_response_text = (outcome.raw_response_text or "").strip()
    if not raw_response_text:
        raw_response_text = _read_raw_text(outcome.raw_text_path)
    if raw_response_text:
        parsed = parse_valuecell_text(raw_response_text)

    if outcome.status == "completed":
        summary = parsed["summary"] or "Execution completed in attached browser session."
    else:
        summary = parsed["summary"] or "Execution requires manual intervention to recover browser session."

    return FinalResult(
        task_id=outcome.task_id,
        status=outcome.status,
        summary=summary,
        highlights=parsed["highlights"],
        table=parsed["table"],
        risk_rating=parsed["risk_rating"],
        raw_sources=[outcome.raw_text_path] if outcome.raw_text_path else [],
        screenshots=[outcome.screenshot_path] if outcome.screenshot_path else [],
        valuecell_raw_response=raw_response_text or None,
        prompt_chain_status=prompt_chain_status,
        llm_mode=llm_mode,
        llm_fallback_reason=llm_fallback_reason,
        failed_step=outcome.failed_step,
        error_message=outcome.error_message,
    )


def _read_raw_text(raw_text_path: str | None) -> str:
    if raw_text_path is None:
        return ""
    from pathlib import Path

    path = Path(raw_text_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
