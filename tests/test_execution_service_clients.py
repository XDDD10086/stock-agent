from app.orchestrator.execution_service import build_llm_clients_from_env
from app.orchestrator.execution_service import (
    DeterministicFinalizerClient,
    DeterministicPlannerClient,
    DeterministicReviewerClient,
)


def test_build_llm_clients_defaults_to_deterministic(monkeypatch):
    monkeypatch.setenv("USE_LIVE_LLM", "false")

    planner, reviewer, finalizer = build_llm_clients_from_env()

    assert isinstance(planner, DeterministicPlannerClient)
    assert isinstance(reviewer, DeterministicReviewerClient)
    assert isinstance(finalizer, DeterministicFinalizerClient)
