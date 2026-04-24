from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.discord_bridge.api_client import ApiClientError
from app.discord_bridge.config import BridgeConfig
from app.discord_bridge.policy import CommandContext
from app.discord_bridge.service import BridgeService
from app.discord_bridge.state_store import DeliveryStateStore


class FakeApiClient:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.get_artifact_calls: list[str] = []
        self.tasks = {
            "task_manual": {
                "task_id": "task_manual",
                "status": "completed",
                "created_at": (now - timedelta(minutes=2)).isoformat(),
                "updated_at": (now - timedelta(minutes=1, seconds=55)).isoformat(),
                "input": "manual",
            },
            "task_schedule": {
                "task_id": "task_schedule",
                "status": "completed",
                "created_at": (now - timedelta(minutes=1)).isoformat(),
                "updated_at": (now - timedelta(seconds=55)).isoformat(),
                "input": "scheduled",
            },
        }
        self.results = {
            "task_manual": {
                "task_id": "task_manual",
                "status": "completed",
                "summary": "manual summary",
                "risk_rating": "yellow",
                "highlights": ["m1"],
                "failed_step": None,
                "error_message": None,
            },
            "task_schedule": {
                "task_id": "task_schedule",
                "status": "completed",
                "summary": "scheduled summary",
                "risk_rating": "green",
                "highlights": ["s1"],
                "failed_step": None,
                "error_message": None,
            },
        }
        self.trigger_meta = {
            "task_schedule": {"source": "schedule", "schedule_id": 9},
        }

    async def create_task(self, prompt: str) -> dict:
        return {"task_id": "task_manual", "status": "created", "input": prompt}

    async def run_task(self, task_id: str) -> dict:
        return self.results[task_id]

    async def list_tasks(self) -> list[dict]:
        return list(self.tasks.values())

    async def get_result(self, task_id: str) -> dict:
        return self.results[task_id]

    async def get_artifact(self, task_id: str, artifact_type: str) -> dict | None:
        if artifact_type != "trigger_meta":
            return None
        self.get_artifact_calls.append(task_id)
        return self.trigger_meta.get(task_id)


class FakeTransport:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str | None, dict | None]] = []

    async def send_channel_message(self, channel_id: int, content: str | None = None, embed: dict | None = None) -> None:
        self.messages.append((channel_id, content, embed))


class BusyApiClient(FakeApiClient):
    def __init__(self) -> None:
        super().__init__()
        now = datetime.now(UTC)
        self.tasks["task_running"] = {
            "task_id": "task_running",
            "status": "running",
            "created_at": (now - timedelta(minutes=1)).isoformat(),
            "updated_at": now.isoformat(),
            "input": "running task",
        }
        self.create_task_called = False

    async def create_task(self, prompt: str) -> dict:
        self.create_task_called = True
        return await super().create_task(prompt)


class StaleRunningApiClient(BusyApiClient):
    def __init__(self) -> None:
        super().__init__()
        stale = datetime.now(UTC) - timedelta(hours=2)
        self.tasks["task_running"]["created_at"] = stale.isoformat()
        self.tasks["task_running"]["updated_at"] = stale.isoformat()


async def _run(service: BridgeService, ctx: CommandContext) -> None:
    await service.execute_run(prompt="check portfolio", context=ctx)


def _config(state_path: str) -> BridgeConfig:
    return BridgeConfig(
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
        admin_user_ids={7000},
        schedule_allow_everyone=True,
        cancel_by_name_allowed=True,
        task_watch_interval_seconds=5,
        task_watch_lookback_minutes=180,
        delivery_state_path=state_path,
        http_timeout_seconds=30,
    )


def test_execute_run_posts_result_to_analyst_channel(tmp_path: Path):
    cfg = _config(str(tmp_path / "state.json"))
    state = DeliveryStateStore(cfg.delivery_state_path)
    transport = FakeTransport()
    service = BridgeService(config=cfg, api_client=FakeApiClient(), transport=transport, state_store=state)

    ctx = CommandContext(channel_id=100, user_id=11, role_ids=set())
    asyncio.run(_run(service, ctx))

    assert transport.messages
    channel_id, _, embed = transport.messages[-1]
    assert channel_id == 100
    assert embed is not None
    assert embed["title"] == "Manual Run Result"


def test_poll_schedule_results_posts_once_and_dedupes(tmp_path: Path):
    cfg = _config(str(tmp_path / "state.json"))
    state = DeliveryStateStore(cfg.delivery_state_path)
    transport = FakeTransport()
    service = BridgeService(config=cfg, api_client=FakeApiClient(), transport=transport, state_store=state)
    api = service._api  # test helper: inspect fake call behavior

    asyncio.run(service.poll_scheduled_results())
    assert len(transport.messages) == 1
    assert transport.messages[0][0] == 100
    assert transport.messages[0][2]["title"] == "Scheduled Run Result"
    assert api.get_artifact_calls.count("task_manual") == 1

    # Poll again; should not duplicate.
    asyncio.run(service.poll_scheduled_results())
    assert len(transport.messages) == 1
    assert api.get_artifact_calls.count("task_manual") == 1


def test_execute_run_short_circuits_when_runner_is_busy(tmp_path: Path):
    cfg = _config(str(tmp_path / "state.json"))
    state = DeliveryStateStore(cfg.delivery_state_path)
    transport = FakeTransport()
    api = BusyApiClient()
    service = BridgeService(config=cfg, api_client=api, transport=transport, state_store=state)

    ctx = CommandContext(channel_id=100, user_id=11, role_ids=set())
    try:
        asyncio.run(service.execute_run(prompt="should not create task while busy", context=ctx))
    except ApiClientError as exc:
        assert exc.status_code == 409
        assert "runner is busy" in exc.detail
    else:
        raise AssertionError("expected ApiClientError busy conflict")

    assert api.create_task_called is False
    assert transport.messages == []


def test_execute_run_ignores_stale_running_rows(tmp_path: Path):
    cfg = _config(str(tmp_path / "state.json"))
    state = DeliveryStateStore(cfg.delivery_state_path)
    transport = FakeTransport()
    api = StaleRunningApiClient()
    service = BridgeService(config=cfg, api_client=api, transport=transport, state_store=state)

    ctx = CommandContext(channel_id=100, user_id=11, role_ids=set())
    result = asyncio.run(service.execute_run(prompt="stale-running-should-not-block", context=ctx))
    assert result["status"] == "completed"
    assert api.create_task_called is True
