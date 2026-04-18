from app.orchestrator.finalize_service import FinalizeService
from app.orchestrator.planner_service import PlannerService
from app.orchestrator.review_service import ReviewService
from app.schemas.execution_pack import ExecutionPack
from app.schemas.plan import PlanV1
from app.schemas.review import ReviewV1


class FakePlannerClient:
    def plan(self, task_input: str) -> dict:
        return {
            "objective": f"Plan for: {task_input}",
            "constraints": ["use valuecell"],
            "required_outputs": ["summary", "risk_rating"],
            "steps": ["collect data", "summarize"],
            "risk_flags": [],
            "needs_review": True,
        }


class FakeReviewerClient:
    def review(self, plan: dict) -> dict:
        return {
            "approved": False,
            "missing_items": ["missing ticker universe"],
            "ambiguities": [],
            "risk_flags": ["insufficient source validation"],
            "suggested_changes": ["add data source scope"],
        }


class FakeFinalizerClient:
    def finalize(self, plan: dict, review: dict) -> dict:
        return {
            "target": "valuecell_web",
            "valuecell_prompt": "run stock risk scan",
            "expected_sections": ["summary", "table", "risk_rating"],
            "browser_steps": [
                {"action": "open_chat"},
                {"action": "fill_prompt", "content": "run stock risk scan"},
                {"action": "submit"},
                {"action": "wait_until_completed"},
            ],
            "timeout_seconds": 900,
        }


def test_planner_service_returns_plan_schema():
    service = PlannerService(client=FakePlannerClient())
    result = service.generate_plan("scan ai hardware portfolio")

    assert isinstance(result, PlanV1)
    assert result.needs_review is True
    assert result.required_outputs == ["summary", "risk_rating"]


def test_review_service_returns_review_schema():
    planner = PlannerService(client=FakePlannerClient())
    plan = planner.generate_plan("scan ai hardware portfolio")
    service = ReviewService(client=FakeReviewerClient())
    result = service.review_plan(plan)

    assert isinstance(result, ReviewV1)
    assert result.approved is False
    assert "missing ticker universe" in result.missing_items


def test_finalize_service_returns_execution_pack_schema():
    planner = PlannerService(client=FakePlannerClient())
    reviewer = ReviewService(client=FakeReviewerClient())
    finalizer = FinalizeService(client=FakeFinalizerClient())

    plan = planner.generate_plan("scan ai hardware portfolio")
    review = reviewer.review_plan(plan)
    result = finalizer.build_execution_pack(plan, review)

    assert isinstance(result, ExecutionPack)
    assert result.target == "valuecell_web"
    assert result.browser_steps[0].action == "open_chat"
