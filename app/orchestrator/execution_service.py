from __future__ import annotations

from datetime import UTC, datetime
import re
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

        detailed_report = _build_deterministic_detailed_report(
            context=context,
            summary=summary,
            actions=deduped_actions[:5],
            review=review,
        )

        return {
            "committee_summary": summary or "已完成二次提炼，建议按风险可控原则分步执行。",
            "committee_actions": deduped_actions[:5],
            "detailed_report": detailed_report,
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
            final_result.committee_report_json = None
            final_result.committee_report_markdown = None
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
                "committee_report_json": final_result.committee_report_json,
                "committee_report_markdown": final_result.committee_report_markdown,
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
            final_result.committee_report_json = final_model.detailed_report
            final_result.committee_report_markdown = _render_committee_report_markdown(final_model.detailed_report)

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
            final_result.committee_report_json = None
            final_result.committee_report_markdown = None

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
            "committee_report_json": final_result.committee_report_json,
            "committee_report_markdown": final_result.committee_report_markdown,
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
        mock_mode=os.getenv("VALUECELL_MOCK_MODE", "off").strip().lower() or "off",
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


def _build_deterministic_detailed_report(*, context: dict, summary: str, actions: list[dict], review: dict) -> dict:
    parsed = context.get("parsed_result", {})
    raw_text = str(context.get("valuecell_raw_response") or "")
    risk_rating = str(parsed.get("risk_rating", "unknown")).lower()
    numeric_tokens = _extract_numeric_tokens(raw_text, limit=16)
    key_points = []
    for token in numeric_tokens[:6]:
        key_points.append({"point": f"关键数字跟踪：{token}", "supporting_numbers": [token]})
    if not key_points:
        key_points = [
            {
                "point": "材料未提供足够结构化数字，需补充更明确的估值与资金流数据。",
                "supporting_numbers": [],
            }
        ]

    focus_items = []
    for item in actions[:5]:
        action = str(item.get("action", "")).strip()
        if action:
            focus_items.append(action)
    if not focus_items:
        focus_items = ["未来 5 个交易日优先观察资金流与风险评级变化"]

    overview_row = {
        "ticker": "材料未提供，暂无法确认",
        "name": "组合层面",
        "core_logic": "根据 ValueCell 与 committee 综合判断，执行分步验证与风险收敛。",
        "valuation": {
            "pe_ttm": None,
            "pb": None,
            "notes": "材料未提供，暂无法确认",
        },
        "fundamentals": {
            "net_profit_growth": None,
            "debt_ratio": None,
            "operating_cashflow": None,
            "interest_bearing_debt": None,
            "notes": "材料未提供，暂无法确认",
        },
        "main_risks": [f"当前风险评级：{risk_rating}"],
        "preliminary_action": "观察",
        "confidence": "medium",
    }

    valuecell_review = {
        "adoptable_conclusions": [
            {
                "conclusion": "风险拆解框架可直接采纳",
                "reason": "包含风险评级与多维信号，具备执行参考价值。",
                "supporting_numbers": numeric_tokens[:4],
            }
        ],
        "cautious_conclusions": [
            {
                "conclusion": "部分强结论需谨慎",
                "reason": "存在“情绪/资金驱动”占比较高情况，需二次验证。",
                "supporting_numbers": numeric_tokens[4:8],
            }
        ],
        "unconfirmed_conclusions": [
            {
                "conclusion": "精确价格位止损",
                "missing_data": "材料未提供连续价格序列与关键技术位",
                "notes": "材料未提供，暂无法确认",
            }
        ],
    }

    single_name_actions = []
    for item in actions[:4]:
        action = str(item.get("action", "")).strip()
        reason = str(item.get("reason", "")).strip() or "基于当前研究信号给出的执行建议。"
        single_name_actions.append(
            {
                "ticker": "材料未提供，暂无法确认",
                "name": "待跟踪标的",
                "current_judgment": action or "保持观察",
                "supporting_numbers": numeric_tokens[:3],
                "next_5d_watch_items": [
                    {
                        "watch_item": "资金流与风险评级是否同向改善",
                        "why_it_matters": "用于验证当前建议是否具备持续性。",
                        "threshold_or_signal": "若连续 2 日信号改善，执行计划动作；反之保持观察。",
                        "data_gap_note": "材料未提供统一阈值口径，暂用条件触发表达。",
                    }
                ],
                "bull_case": "核心风险指标改善，资金流延续，策略可逐步推进。",
                "bear_case": "风险指标恶化或资金流反转，需降低风险暴露。",
                "recommended_action": action or "观察",
                "risk_control_triggers": [
                    {
                        "trigger": "风险评级上行或负面资金流连续出现",
                        "action_if_triggered": "执行保护性减仓并提高现金/低波配置占比。",
                    }
                ],
                "notes": reason,
            }
        )
    if not single_name_actions:
        single_name_actions.append(
            {
                "ticker": "材料未提供，暂无法确认",
                "name": "待跟踪标的",
                "current_judgment": "观察",
                "supporting_numbers": numeric_tokens[:3],
                "next_5d_watch_items": [
                    {
                        "watch_item": "组合层面风险评级",
                        "why_it_matters": "用于判断是否需要整体降风险。",
                        "threshold_or_signal": "若风险评级转差并持续 2 日，执行保护性减仓。",
                        "data_gap_note": "材料未提供，暂无法确认价格阈值。",
                    }
                ],
                "bull_case": "风险缓释与资金修复同步出现。",
                "bear_case": "风险加剧且资金承接不足。",
                "recommended_action": "观察",
                "risk_control_triggers": [
                    {
                        "trigger": "风险评级转差",
                        "action_if_triggered": "降低高波动暴露。",
                    }
                ],
                "notes": "材料未提供，暂无法确认标的级别完整数据。",
            }
        )

    next_5d_action_plan = []
    for idx, item in enumerate(actions[:5], start=1):
        action = str(item.get("action", "")).strip() or "执行风险复核"
        next_5d_action_plan.append(
            {
                "target": f"观察对象 {idx}",
                "indicator": "资金流/风险评级/预期变化",
                "threshold": "连续 2 日同向变化",
                "action_if_triggered": action,
                "action_if_not_triggered": "维持观察并等待下一批验证数据",
                "priority": "high" if idx <= 2 else "medium",
            }
        )
    if not next_5d_action_plan:
        next_5d_action_plan.append(
            {
                "target": "组合层面",
                "indicator": "风险评级变化",
                "threshold": "连续 2 日转差",
                "action_if_triggered": "执行保护性减仓",
                "action_if_not_triggered": "维持观察",
                "priority": "high",
            }
        )

    review_issues = list(review.get("issues") or [])
    review_safety = list(review.get("safety_notes") or [])
    return {
        "report_status": "completed",
        "report_type": "portfolio_risk_diagnosis_execution_report",
        "report_title": "投资组合风险诊断与执行建议报告",
        "executive_summary": {
            "summary_text": summary or "已完成 committee 综合审查，建议按风险约束分步执行。",
            "key_points": key_points,
            "top_5d_focus": focus_items,
        },
        "portfolio_overview": [overview_row],
        "valuecell_review": valuecell_review,
        "single_name_actions": single_name_actions,
        "next_5d_action_plan": next_5d_action_plan,
        "risk_and_positioning": {
            "portfolio_risk_level": _risk_level_from_rating(risk_rating),
            "reduce_gross_exposure": risk_rating in {"red", "yellow"},
            "priority_positions_to_handle": [item.get("action", "观察") for item in actions[:2]],
            "drawdown_control_rules": [
                {
                    "rule": "风险评级转差优先降风险",
                    "trigger": "风险评级连续 2 日恶化",
                    "action": "优先降低高波动资产暴露并提升防守仓位。",
                }
            ],
            "notes": "; ".join([*review_issues, *review_safety]) or "材料未提供，暂无法确认更细颗粒度仓位参数。",
        },
        "final_committee_conclusion": {
            "largest_risk_exposure": "高波动风险敞口与信号不一致带来的回撤风险",
            "assets_to_keep": ["材料未提供，暂无法确认"],
            "assets_to_reduce": ["材料未提供，暂无法确认"],
            "most_important_5d_discipline": "以信号触发执行，避免主观放大仓位。",
        },
    }


def _extract_numeric_tokens(text: str, *, limit: int) -> list[str]:
    if not text.strip():
        return []
    pattern = re.compile(r"(?:[+-]?\d+(?:\.\d+)?(?:%|倍|亿|万)?|¥\d+(?:\.\d+)?)")
    found = pattern.findall(text)
    deduped: list[str] = []
    for token in found:
        cleaned = token.strip()
        if cleaned in deduped:
            continue
        deduped.append(cleaned)
        if len(deduped) >= limit:
            break
    return deduped


def _risk_level_from_rating(risk_rating: str) -> str:
    rating = (risk_rating or "").lower()
    if rating == "red":
        return "高"
    if rating == "yellow":
        return "中高"
    if rating == "green":
        return "中"
    return "中"


def _render_committee_report_markdown(report: dict) -> str:
    title = str(report.get("report_title") or "投资组合风险诊断与执行建议报告")
    lines = [f"# {title}", ""]

    exec_summary = report.get("executive_summary") or {}
    lines.append("## 1. 执行摘要")
    lines.append(str(exec_summary.get("summary_text") or "材料未提供，暂无法确认"))
    lines.append("")
    key_points = exec_summary.get("key_points") or []
    if key_points:
        for item in key_points:
            point = str(item.get("point") or "").strip()
            numbers = item.get("supporting_numbers") or []
            suffix = f"（数字：{', '.join(map(str, numbers))}）" if numbers else ""
            if point:
                lines.append(f"- {point}{suffix}")
        lines.append("")

    lines.append("## 2. 组合现状总览")
    lines.append(_markdown_table(report.get("portfolio_overview") or []))
    lines.append("")

    lines.append("## 3. ValueCell 结论的有效性审查")
    valuecell_review = report.get("valuecell_review") or {}
    lines.append("### 3.1 可以直接采纳的结论")
    lines.extend(_markdown_list_from_items(valuecell_review.get("adoptable_conclusions") or []))
    lines.append("### 3.2 需要谨慎看待的结论")
    lines.extend(_markdown_list_from_items(valuecell_review.get("cautious_conclusions") or []))
    lines.append("### 3.3 当前无法确认的结论")
    lines.extend(_markdown_list_from_items(valuecell_review.get("unconfirmed_conclusions") or []))
    lines.append("")

    lines.append("## 4. 单标的深度执行建议")
    for idx, item in enumerate(report.get("single_name_actions") or [], start=1):
        name = str(item.get("name") or "待跟踪标的")
        ticker = str(item.get("ticker") or "N/A")
        lines.append(f"### 4.{idx} {name}（{ticker}）")
        lines.append(f"- 当前核心判断：{item.get('current_judgment', '材料未提供，暂无法确认')}")
        numbers = item.get("supporting_numbers") or []
        lines.append(f"- 支持数字：{', '.join(map(str, numbers)) if numbers else '材料未提供，暂无法确认'}")
        lines.append(f"- 建议动作：{item.get('recommended_action', '观察')}")
        triggers = item.get("risk_control_triggers") or []
        if triggers:
            lines.append("- 风控触发：")
            for trigger in triggers:
                lines.append(
                    f"  - 若 {trigger.get('trigger', '条件触发')}，则 {trigger.get('action_if_triggered', '执行保护动作')}"
                )
        lines.append("")

    lines.append("## 5. 未来 5 个交易日行动清单")
    lines.append(_markdown_table(report.get("next_5d_action_plan") or []))
    lines.append("")

    lines.append("## 6. 仓位与回撤控制建议")
    risk_and_positioning = report.get("risk_and_positioning") or {}
    lines.append(f"- 当前组合风险等级：{risk_and_positioning.get('portfolio_risk_level', '中')}")
    lines.append(f"- 是否建议降总风险暴露：{risk_and_positioning.get('reduce_gross_exposure', '材料未提供，暂无法确认')}")
    lines.append(
        f"- 优先处理仓位：{', '.join(risk_and_positioning.get('priority_positions_to_handle') or ['材料未提供，暂无法确认'])}"
    )
    lines.append(f"- 说明：{risk_and_positioning.get('notes', '材料未提供，暂无法确认')}")
    lines.append("")

    lines.append("## 7. 最终结论")
    final_conclusion = report.get("final_committee_conclusion") or {}
    lines.append(f"1. 组合当前最大的风险暴露是什么？{final_conclusion.get('largest_risk_exposure', '材料未提供，暂无法确认')}")
    lines.append(
        f"2. 哪些资产值得保留？{', '.join(final_conclusion.get('assets_to_keep') or ['材料未提供，暂无法确认'])}"
    )
    lines.append(
        f"3. 哪些资产应优先降仓？{', '.join(final_conclusion.get('assets_to_reduce') or ['材料未提供，暂无法确认'])}"
    )
    lines.append(
        f"4. 未来 5 个交易日最重要的一条执行纪律是什么？{final_conclusion.get('most_important_5d_discipline', '材料未提供，暂无法确认')}"
    )
    return "\n".join(lines)


def _markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "材料未提供，暂无法确认"
    columns: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in columns:
                columns.append(str(key))
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    body_lines = []
    for row in rows:
        values = []
        for key in columns:
            value = row.get(key)
            if isinstance(value, list):
                values.append(", ".join(map(str, value)))
            elif isinstance(value, dict):
                values.append("; ".join(f"{k}:{v}" for k, v in value.items()))
            else:
                values.append(str(value) if value is not None else "")
        body_lines.append("| " + " | ".join(values) + " |")
    return "\n".join([header, divider, *body_lines])


def _markdown_list_from_items(items: list[dict]) -> list[str]:
    if not items:
        return ["- 材料未提供，暂无法确认"]
    lines: list[str] = []
    for item in items:
        parts = []
        for key in ("conclusion", "reason", "missing_data", "notes"):
            value = str(item.get(key) or "").strip()
            if value:
                parts.append(value)
        if parts:
            lines.append(f"- {'；'.join(parts)}")
        else:
            lines.append("- 材料未提供，暂无法确认")
    return lines
