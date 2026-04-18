from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import create_app
from app.orchestrator.execution_service import release_execution_lock, try_acquire_execution_lock


class FakeBrowserAdapter:
    def connect(self, cdp_url: str) -> None:
        return None

    def open_chat(self, chat_url: str) -> None:
        return None

    def submit_prompt(self, prompt: str) -> None:
        return None

    def wait_until_completed(self, timeout_seconds: int, poll_interval_seconds: int) -> None:
        return None

    def capture_screenshot(self, output_path: str) -> None:
        with open(output_path, "wb") as f:
            f.write(b"PNG")

    def capture_latest_response_text(self) -> str:
        return (
            "Executive Summary: Portfolio risk has stabilized with improving margins.\n\n"
            "Highlights:\n"
            "- Revenue trend stabilized\n"
            "- Margin recovered\n"
            "Risk Rating: Yellow\n"
        )

    def capture_page_text(self) -> str:
        return (
            "Executive Summary: Portfolio risk has stabilized with improving margins.\n\n"
            "Highlights:\n"
            "- Revenue trend stabilized\n"
            "- Margin recovered\n"
            "Risk Rating: Yellow\n"
        )

    def close(self) -> None:
        return None


class RevisionPlannerClient:
    def plan(self, task_input: str) -> dict:
        return {
            "objective": f"Research objective for {task_input}",
            "constraints": ["research only"],
            "required_outputs": ["summary", "table", "risk_rating"],
            "steps": ["prepare prompt", "submit", "summarize"],
            "risk_flags": ["data_freshness"],
            "needs_review": True,
        }


class RevisionReviewerClient:
    def review(self, plan: dict) -> dict:
        return {
            "approved": False,
            "missing_items": ["add scenario watchpoints"],
            "ambiguities": ["time horizon unclear"],
            "risk_flags": ["event_risk"],
            "suggested_changes": ["add 5-day watchlist"],
        }


class RevisionFinalizerClient:
    def finalize(self, plan: dict, review: dict) -> dict:
        return {
            "target": "valuecell_web",
            "valuecell_prompt": plan["objective"],
            "expected_sections": ["summary", "table", "risk_rating"],
            "browser_steps": [
                {"action": "open_chat"},
                {"action": "fill_prompt", "content": plan["objective"]},
                {"action": "submit"},
                {"action": "wait_until_completed"},
            ],
            "timeout_seconds": 900,
        }


class FailingLivePlannerClient:
    def plan(self, task_input: str) -> dict:
        raise RuntimeError("insufficient_quota")


def _client(db_url: str | None = None) -> TestClient:
    if db_url is None:
        db_url = f"sqlite:///./data/test_app_{uuid4().hex}.db"
    app = create_app(db_url=db_url, adapter_factory=lambda: FakeBrowserAdapter())
    return TestClient(app)


def test_create_task_returns_created_task():
    client = _client()

    response = client.post("/tasks", json={"input": "scan semiconductor portfolio"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"]
    assert payload["status"] == "created"
    assert payload["input"] == "scan semiconductor portfolio"


def test_get_task_returns_task_details():
    client = _client()
    created = client.post("/tasks", json={"input": "daily hardware scan"}).json()

    response = client.get(f"/tasks/{created['task_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == created["task_id"]
    assert payload["status"] == "created"
    assert payload["input"] == "daily hardware scan"


def test_list_tasks_returns_newest_first():
    client = _client()
    first = client.post("/tasks", json={"input": "first"}).json()
    second = client.post("/tasks", json={"input": "second"}).json()

    response = client.get("/tasks")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) >= 2
    assert payload["items"][0]["task_id"] == second["task_id"]
    assert payload["items"][1]["task_id"] == first["task_id"]


def test_health_endpoint():
    client = _client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_and_result_endpoints():
    client = _client()
    created = client.post("/tasks", json={"input": "scan daily portfolio"}).json()

    run_response = client.post(f"/tasks/{created['task_id']}/run")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "completed"
    assert run_payload["task_id"] == created["task_id"]
    assert run_payload["risk_rating"] == "yellow"
    assert len(run_payload["highlights"]) >= 2
    assert run_payload["valuecell_raw_response"]
    assert run_payload["prompt_chain_status"] == "direct_pass"
    assert run_payload["llm_mode"] == "deterministic"

    result_response = client.get(f"/tasks/{created['task_id']}/result")
    assert result_response.status_code == 200
    result_payload = result_response.json()
    assert result_payload["status"] == "completed"
    assert result_payload["summary"]
    assert result_payload["risk_rating"] == "yellow"
    assert result_payload["valuecell_raw_response"]
    assert result_payload["prompt_chain_status"] == "direct_pass"
    assert result_payload["llm_mode"] == "deterministic"

    artifacts_response = client.get(f"/tasks/{created['task_id']}/artifacts")
    assert artifacts_response.status_code == 200
    artifact_types = artifacts_response.json()["artifact_types"]
    assert "plan_v1" in artifact_types
    assert "review_v1" in artifact_types
    assert "execution_pack" in artifact_types
    assert "prompt_chain" in artifact_types
    assert "runner_diagnostics" in artifact_types
    assert "valuecell_raw_response" in artifact_types
    assert "orchestration_metrics" in artifact_types
    assert "final_result" in artifact_types

    plan_artifact = client.get(f"/tasks/{created['task_id']}/artifacts/plan_v1")
    assert plan_artifact.status_code == 200
    assert "结构化结论" in plan_artifact.json()["payload"]["objective"]

    diagnostics_artifact = client.get(f"/tasks/{created['task_id']}/artifacts/runner_diagnostics")
    assert diagnostics_artifact.status_code == 200
    assert diagnostics_artifact.json()["payload"]["status"] == "completed"
    assert diagnostics_artifact.json()["payload"]["duration_seconds"] is not None
    assert diagnostics_artifact.json()["payload"]["step_history"]
    assert diagnostics_artifact.json()["payload"]["raw_response_chars"] > 0

    prompt_chain_artifact = client.get(f"/tasks/{created['task_id']}/artifacts/prompt_chain")
    assert prompt_chain_artifact.status_code == 200
    assert prompt_chain_artifact.json()["payload"]["review_gate_status"] == "direct_pass"
    assert prompt_chain_artifact.json()["payload"]["final_prompt"] != "scan daily portfolio"
    assert prompt_chain_artifact.json()["payload"]["llm_mode"] == "deterministic"

    orchestration_artifact = client.get(f"/tasks/{created['task_id']}/artifacts/orchestration_metrics")
    assert orchestration_artifact.status_code == 200
    metrics = orchestration_artifact.json()["payload"]
    assert metrics["total_seconds"] >= 0
    assert metrics["runner_seconds"] >= 0


def test_run_endpoint_returns_409_when_runner_busy():
    client = _client()
    created = client.post("/tasks", json={"input": "scan daily portfolio"}).json()
    acquired = try_acquire_execution_lock()
    assert acquired is True

    try:
        response = client.post(f"/tasks/{created['task_id']}/run")
    finally:
        release_execution_lock()

    assert response.status_code == 409
    assert response.json()["detail"] == "runner is busy"


def test_prompt_gate_revises_once_when_review_not_approved(monkeypatch):
    monkeypatch.setattr(
        "app.orchestrator.execution_service.build_llm_clients_from_env",
        lambda: (RevisionPlannerClient(), RevisionReviewerClient(), RevisionFinalizerClient()),
    )
    client = _client()
    created = client.post("/tasks", json={"input": "simple intent"}).json()

    run_response = client.post(f"/tasks/{created['task_id']}/run")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["prompt_chain_status"] == "revised_once"

    prompt_chain = client.get(f"/tasks/{created['task_id']}/artifacts/prompt_chain")
    assert prompt_chain.status_code == 200
    chain_payload = prompt_chain.json()["payload"]
    assert chain_payload["review_gate_status"] == "revised_once"
    assert chain_payload["revised_plan"] is not None
    assert chain_payload["final_prompt"] != "simple intent"
    assert "(review-adjusted)" in chain_payload["final_prompt"]


def test_live_llm_failure_falls_back_to_deterministic(monkeypatch):
    monkeypatch.setattr(
        "app.orchestrator.execution_service.resolve_llm_mode_from_env",
        lambda: "live",
    )
    monkeypatch.setattr(
        "app.orchestrator.execution_service.build_llm_clients_from_env",
        lambda: (FailingLivePlannerClient(), RevisionReviewerClient(), RevisionFinalizerClient()),
    )
    client = _client()
    created = client.post("/tasks", json={"input": "fallback check"}).json()

    run_response = client.post(f"/tasks/{created['task_id']}/run")
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["status"] == "completed"
    assert payload["llm_mode"] == "live_fallback_deterministic"
    assert payload["llm_fallback_reason"]

    prompt_chain = client.get(f"/tasks/{created['task_id']}/artifacts/prompt_chain")
    assert prompt_chain.status_code == 200
    chain_payload = prompt_chain.json()["payload"]
    assert chain_payload["llm_mode"] == "live_fallback_deterministic"
    assert chain_payload["llm_fallback_reason"]

    llm_live_error = client.get(f"/tasks/{created['task_id']}/artifacts/llm_live_error")
    assert llm_live_error.status_code == 200
    assert llm_live_error.json()["payload"]["error_type"] == "RuntimeError"
