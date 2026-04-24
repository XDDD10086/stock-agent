from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.discord_bridge.api_client import ApiClientError
from app.discord_bridge.config import BridgeConfig
from app.discord_bridge.formatter import build_final_result_embed, build_schedule_list_embed
from app.discord_bridge.policy import BridgePolicy, CommandContext, resolve_schedule_target
from app.discord_bridge.state_store import DeliveryStateStore


class BridgeApiClient(Protocol):
    async def create_task(self, prompt: str) -> dict: ...

    async def run_task(self, task_id: str) -> dict: ...

    async def list_tasks(self) -> list[dict]: ...

    async def get_result(self, task_id: str) -> dict: ...

    async def get_artifact(self, task_id: str, artifact_type: str) -> dict | None: ...

    async def create_schedule(self, payload: dict) -> dict: ...

    async def list_schedules(self) -> list[dict]: ...

    async def delete_schedule(self, schedule_id: int) -> dict: ...

    async def pause_schedule(self, schedule_id: int) -> dict: ...

    async def resume_schedule(self, schedule_id: int) -> dict: ...

    async def run_schedule_once(self, schedule_id: int) -> dict: ...


class BridgeTransport(Protocol):
    async def send_channel_message(self, channel_id: int, content: str | None = None, embed: dict | None = None) -> None: ...


class BridgeService:
    def __init__(
        self,
        *,
        config: BridgeConfig,
        api_client: BridgeApiClient,
        transport: BridgeTransport,
        state_store: DeliveryStateStore,
    ) -> None:
        self.config = config
        self.policy = BridgePolicy(config)
        self._api = api_client
        self._transport = transport
        self._state = state_store

    async def execute_run(self, *, prompt: str, context: CommandContext) -> dict:
        allowed, reason = self.policy.authorize_run(context)
        if not allowed:
            raise PermissionError(reason)
        if await self._is_runner_busy():
            raise ApiClientError(409, "runner is busy")

        created = await self._api.create_task(prompt)
        task_id = str(created.get("task_id", "")).strip()
        if not task_id:
            raise RuntimeError("create_task did not return task_id")

        result = await self._api.run_task(task_id)
        await self._post_result_to_analyst(result, title="Manual Run Result")
        return result

    async def create_schedule(self, *, payload: dict, context: CommandContext) -> dict:
        self._assert_schedule_authorized(context)
        return await self._api.create_schedule(payload)

    async def list_schedules(self, *, context: CommandContext) -> list[dict]:
        self._assert_schedule_authorized(context)
        return await self._api.list_schedules()

    async def cancel_schedule(self, *, target: str, context: CommandContext) -> dict:
        self._assert_schedule_authorized(context)
        schedule_id = await self._resolve_schedule_target(target)
        return await self._api.delete_schedule(schedule_id)

    async def pause_schedule(self, *, target: str, context: CommandContext) -> dict:
        self._assert_schedule_authorized(context)
        schedule_id = await self._resolve_schedule_target(target)
        return await self._api.pause_schedule(schedule_id)

    async def resume_schedule(self, *, target: str, context: CommandContext) -> dict:
        self._assert_schedule_authorized(context)
        schedule_id = await self._resolve_schedule_target(target)
        return await self._api.resume_schedule(schedule_id)

    async def run_schedule_once(self, *, target: str, context: CommandContext) -> dict:
        self._assert_schedule_authorized(context)
        schedule_id = await self._resolve_schedule_target(target)
        result = await self._api.run_schedule_once(schedule_id)
        await self._post_result_to_analyst(result, title="Scheduled Run Result")
        task_id = str(result.get("task_id") or "").strip()
        if task_id:
            self._state.mark_delivered(task_id)
        return result

    async def poll_scheduled_results(self) -> int:
        tasks = await self._api.list_tasks()
        delivered_count = 0
        lookback_floor = datetime.now(UTC) - timedelta(minutes=self.config.task_watch_lookback_minutes)

        for task in tasks:
            task_id = str(task.get("task_id") or "").strip()
            if not task_id:
                continue
            if self._state.is_delivered(task_id):
                continue
            if str(task.get("status")) not in {"completed", "needs_manual_intervention"}:
                continue
            if not _is_within_lookback(task, lookback_floor):
                continue

            trigger_meta = await self._api.get_artifact(task_id, "trigger_meta")
            if not trigger_meta:
                # Not a scheduled run; mark once so watcher does not re-fetch forever.
                self._state.mark_delivered(task_id)
                continue
            source = str(trigger_meta.get("source", "")).lower()
            if not source.startswith("schedule"):
                # Manual runs are out of scope for scheduler watcher delivery.
                self._state.mark_delivered(task_id)
                continue

            result = await self._api.get_result(task_id)
            await self._post_result_to_analyst(result, title="Scheduled Run Result")
            self._state.mark_delivered(task_id)
            delivered_count += 1

        return delivered_count

    def build_schedule_list_embed(self, items: list[dict]) -> dict:
        return build_schedule_list_embed(items)

    async def send_text_message(self, channel_id: int, content: str) -> None:
        await self._transport.send_channel_message(channel_id, content=content)

    def _assert_schedule_authorized(self, context: CommandContext) -> None:
        allowed, reason = self.policy.authorize_schedule(context)
        if not allowed:
            raise PermissionError(reason)

    async def _resolve_schedule_target(self, target: str) -> int:
        normalized = target.strip()
        if not normalized:
            raise ValueError("schedule target is required")
        if not self.config.cancel_by_name_allowed and not normalized.isdigit():
            raise ValueError("name-based target is disabled; please use schedule id")

        schedules = await self._api.list_schedules()
        return resolve_schedule_target(normalized, schedules)

    async def _post_result_to_analyst(self, payload: dict, *, title: str) -> None:
        if self.config.response_format == "embed":
            embed = build_final_result_embed(payload, title=title)
            await self._transport.send_channel_message(self.config.result_channel_id, embed=embed)
            return

        summary = str(payload.get("summary") or "")
        status = str(payload.get("status") or "unknown")
        task_id = str(payload.get("task_id") or "-")
        text = f"[{title}] task={task_id} status={status}\n{summary}".strip()
        await self._transport.send_channel_message(self.config.result_channel_id, content=text)

    async def _is_runner_busy(self) -> bool:
        tasks = await self._api.list_tasks()
        running_tasks = [item for item in tasks if str(item.get("status") or "").lower() == "running"]
        if not running_tasks:
            return False

        # Treat very old "running" rows as stale leftovers (e.g., process restart mid-run)
        # so they do not block new runs forever.
        busy_floor = datetime.now(UTC) - timedelta(minutes=30)
        for task in running_tasks:
            raw = task.get("updated_at") or task.get("created_at")
            if raw is None:
                return True
            timestamp = _parse_datetime(str(raw))
            if timestamp is None:
                return True
            if timestamp >= busy_floor:
                return True
        return False


def _is_within_lookback(task: dict, lookback_floor: datetime) -> bool:
    raw = task.get("updated_at") or task.get("created_at")
    if raw is None:
        return True
    timestamp = _parse_datetime(str(raw))
    if timestamp is None:
        return True
    return timestamp >= lookback_floor


def _parse_datetime(value: str) -> datetime | None:
    try:
        normalized = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None
