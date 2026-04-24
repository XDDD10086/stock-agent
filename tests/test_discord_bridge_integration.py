from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.orchestrator.execution_service import release_execution_lock, try_acquire_execution_lock
from app.discord_bridge.api_client import ApiClientError
from app.discord_bridge.config import BridgeConfig
from app.discord_bridge.policy import CommandContext
from app.discord_bridge.service import BridgeService
from app.discord_bridge.state_store import DeliveryStateStore


class SuccessAdapter:
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
            "Executive Summary: Integration run completed.\n\n"
            "Highlights:\n"
            "- Integration signal\n"
            "Risk Rating: Yellow\n"
        )

    def capture_page_text(self) -> str:
        return self.capture_latest_response_text()

    def close(self) -> None:
        return None


class FailingAdapter(SuccessAdapter):
    def submit_prompt(self, prompt: str) -> None:
        raise RuntimeError("submit_prompt failed")


class SyncApiClient:
    def __init__(self, client: TestClient) -> None:
        self._client = client

    async def create_task(self, prompt: str) -> dict:
        return self._request("POST", "/tasks", {"input": prompt})

    async def run_task(self, task_id: str) -> dict:
        return self._request("POST", f"/tasks/{task_id}/run")

    async def list_tasks(self) -> list[dict]:
        payload = self._request("GET", "/tasks")
        return payload.get("items", [])

    async def get_result(self, task_id: str) -> dict:
        return self._request("GET", f"/tasks/{task_id}/result")

    async def get_artifact(self, task_id: str, artifact_type: str) -> dict | None:
        try:
            payload = self._request("GET", f"/tasks/{task_id}/artifacts/{artifact_type}")
        except ApiClientError as exc:
            if exc.status_code == 404:
                return None
            raise
        return payload.get("payload")

    async def create_schedule(self, payload: dict) -> dict:
        return self._request("POST", "/schedules", payload)

    async def list_schedules(self) -> list[dict]:
        payload = self._request("GET", "/schedules")
        return payload.get("items", [])

    async def delete_schedule(self, schedule_id: int) -> dict:
        return self._request("DELETE", f"/schedules/{schedule_id}")

    async def pause_schedule(self, schedule_id: int) -> dict:
        return self._request("POST", f"/schedules/{schedule_id}/pause")

    async def resume_schedule(self, schedule_id: int) -> dict:
        return self._request("POST", f"/schedules/{schedule_id}/resume")

    async def run_schedule_once(self, schedule_id: int) -> dict:
        return self._request("POST", f"/schedules/{schedule_id}/run-once")

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if method == "GET":
            resp = self._client.get(path)
        elif method == "DELETE":
            resp = self._client.delete(path)
        else:
            resp = self._client.request(method, path, json=payload)

        if resp.status_code >= 400:
            detail = str(resp.json().get("detail", resp.text)) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise ApiClientError(resp.status_code, detail)
        return resp.json()


class FakeTransport:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str | None, dict | None]] = []

    async def send_channel_message(self, channel_id: int, content: str | None = None, embed: dict | None = None) -> None:
        self.messages.append((channel_id, content, embed))


def _build_service(
    *,
    tmp_path: Path,
    adapter_factory,
) -> tuple[BridgeService, SyncApiClient, FakeTransport, TestClient]:
    db_url = f"sqlite:///./data/test_discord_bridge_{uuid4().hex}.db"
    app = create_app(db_url=db_url, adapter_factory=adapter_factory)
    client = TestClient(app)
    api_client = SyncApiClient(client)
    transport = FakeTransport()
    config = BridgeConfig(
        bot_token="token",
        application_id=1,
        guild_id=2,
        allowed_channel_ids={100, 200},
        run_channel_ids={100},
        schedule_channel_ids={200},
        result_channel_id=100,
        api_base_url="http://127.0.0.1:8000",
        response_format="embed",
        longrun_ack=True,
        schedule_manager_role_ids=set(),
        run_role_ids=set(),
        admin_user_ids={999},
        schedule_allow_everyone=True,
        cancel_by_name_allowed=True,
        task_watch_interval_seconds=5,
        task_watch_lookback_minutes=180,
        delivery_state_path=str(tmp_path / "state.json"),
        http_timeout_seconds=30,
    )
    service = BridgeService(
        config=config,
        api_client=api_client,
        transport=transport,
        state_store=DeliveryStateStore(config.delivery_state_path),
    )
    return service, api_client, transport, client


def test_bridge_service_run_and_schedule_crud_flow(tmp_path: Path):
    service, _, transport, _ = _build_service(tmp_path=tmp_path, adapter_factory=lambda: SuccessAdapter())

    run_ctx = CommandContext(channel_id=100, user_id=111, role_ids=set())
    schedule_ctx = CommandContext(channel_id=200, user_id=111, role_ids=set())

    run_result = asyncio.run(service.execute_run(prompt="integration prompt", context=run_ctx))
    assert run_result["status"] == "completed"
    assert any(msg[0] == 100 and msg[2] and msg[2]["title"] == "Manual Run Result" for msg in transport.messages)

    created = asyncio.run(
        service.create_schedule(
            payload={
                "name": "bridge_daily",
                "task_input": "schedule integration",
                "trigger_type": "daily",
                "time_of_day": "10:00",
                "timezone": "America/New_York",
            },
            context=schedule_ctx,
        )
    )
    schedule_id = created["id"]

    listed = asyncio.run(service.list_schedules(context=schedule_ctx))
    assert any(item["id"] == schedule_id for item in listed)

    paused = asyncio.run(service.pause_schedule(target=str(schedule_id), context=schedule_ctx))
    assert paused["enabled"] is False

    resumed = asyncio.run(service.resume_schedule(target=str(schedule_id), context=schedule_ctx))
    assert resumed["enabled"] is True

    run_once_result = asyncio.run(service.run_schedule_once(target=str(schedule_id), context=schedule_ctx))
    assert run_once_result["status"] in {"completed", "needs_manual_intervention"}
    assert any(msg[0] == 100 and msg[2] and msg[2]["title"] == "Scheduled Run Result" for msg in transport.messages)

    deleted = asyncio.run(service.cancel_schedule(target=str(schedule_id), context=schedule_ctx))
    assert deleted["deleted"] is True


def test_bridge_service_surfaces_busy_conflict(tmp_path: Path):
    service, _, _, _ = _build_service(tmp_path=tmp_path, adapter_factory=lambda: SuccessAdapter())
    ctx = CommandContext(channel_id=100, user_id=111, role_ids=set())

    acquired = try_acquire_execution_lock()
    assert acquired is True
    try:
        try:
            asyncio.run(service.execute_run(prompt="busy case", context=ctx))
        except ApiClientError as exc:
            assert exc.status_code == 409
            assert "runner is busy" in exc.detail
        else:
            raise AssertionError("expected busy conflict")
    finally:
        release_execution_lock()


def test_poll_posts_manual_intervention_scheduled_results_once(tmp_path: Path):
    service, api_client, transport, _ = _build_service(tmp_path=tmp_path, adapter_factory=lambda: FailingAdapter())
    schedule_ctx = CommandContext(channel_id=200, user_id=111, role_ids=set())

    created = asyncio.run(
        service.create_schedule(
            payload={
                "name": "bridge_once",
                "task_input": "should fail in runner",
                "trigger_type": "daily",
                "time_of_day": "10:00",
                "timezone": "America/New_York",
            },
            context=schedule_ctx,
        )
    )

    # Trigger directly via API client to emulate scheduler-originated execution.
    run_once = asyncio.run(api_client.run_schedule_once(created["id"]))
    assert run_once["status"] == "needs_manual_intervention"

    delivered = asyncio.run(service.poll_scheduled_results())
    assert delivered == 1
    assert any(msg[0] == 100 and msg[2] and msg[2]["title"] == "Scheduled Run Result" for msg in transport.messages)

    delivered_again = asyncio.run(service.poll_scheduled_results())
    assert delivered_again == 0
