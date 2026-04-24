from app.orchestrator.execution_service import build_llm_clients_from_env
from app.orchestrator.execution_service import (
    DeterministicCommitteeDrafterClient,
    DeterministicCommitteeFinalizerClient,
    DeterministicCommitteeReviewerClient,
    DeterministicFinalizerClient,
    DeterministicPlannerClient,
    DeterministicReviewerClient,
)
from app.orchestrator.execution_service import build_committee_clients_from_env
from app.orchestrator.execution_service import build_runner_config_from_env


def test_build_llm_clients_defaults_to_deterministic(monkeypatch):
    monkeypatch.setenv("USE_LIVE_LLM", "false")

    planner, reviewer, finalizer = build_llm_clients_from_env()

    assert isinstance(planner, DeterministicPlannerClient)
    assert isinstance(reviewer, DeterministicReviewerClient)
    assert isinstance(finalizer, DeterministicFinalizerClient)


def test_build_committee_clients_defaults_to_deterministic(monkeypatch):
    monkeypatch.setenv("USE_LIVE_LLM", "false")

    drafter, reviewer, finalizer = build_committee_clients_from_env(llm_mode="deterministic")

    assert isinstance(drafter, DeterministicCommitteeDrafterClient)
    assert isinstance(reviewer, DeterministicCommitteeReviewerClient)
    assert isinstance(finalizer, DeterministicCommitteeFinalizerClient)


def test_build_runner_config_reads_mock_mode(monkeypatch):
    monkeypatch.setenv("VALUECELL_MOCK_MODE", "pass")

    cfg = build_runner_config_from_env()

    assert cfg.mock_mode == "pass"
