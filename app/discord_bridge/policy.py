from __future__ import annotations

from dataclasses import dataclass

from app.discord_bridge.config import BridgeConfig


@dataclass(frozen=True)
class CommandContext:
    channel_id: int
    user_id: int
    role_ids: set[int]


class BridgePolicy:
    def __init__(self, config: BridgeConfig) -> None:
        self._config = config

    def is_admin(self, context: CommandContext) -> bool:
        return context.user_id in self._config.admin_user_ids

    def authorize_run(self, context: CommandContext) -> tuple[bool, str]:
        if context.channel_id not in self._config.allowed_channel_ids:
            return False, "This channel is not in DISCORD_ALLOWED_CHANNEL_IDS."
        if context.channel_id not in self._config.run_channel_ids:
            return False, "Run command is only allowed in configured run channel(s)."
        if self.is_admin(context):
            return True, "ok"
        if not self._config.run_role_ids:
            return True, "ok"
        if context.role_ids & self._config.run_role_ids:
            return True, "ok"
        return False, "Missing required run role."

    def authorize_schedule(self, context: CommandContext) -> tuple[bool, str]:
        if context.channel_id not in self._config.allowed_channel_ids:
            return False, "This channel is not in DISCORD_ALLOWED_CHANNEL_IDS."
        if context.channel_id not in self._config.schedule_channel_ids:
            return False, "Schedule command is only allowed in configured scheduler channel(s)."
        if self._config.schedule_allow_everyone:
            return True, "ok"
        if self.is_admin(context):
            return True, "ok"
        if not self._config.schedule_manager_role_ids:
            return False, "No scheduler manager role configured."
        if context.role_ids & self._config.schedule_manager_role_ids:
            return True, "ok"
        return False, "Missing required scheduler manager role."


def resolve_schedule_target(target: str, schedules: list[dict]) -> int:
    normalized = target.strip()
    if not normalized:
        raise ValueError("schedule target is required")

    if normalized.isdigit():
        schedule_id = int(normalized)
        for item in schedules:
            if int(item.get("id", -1)) == schedule_id:
                return schedule_id
        raise ValueError(f"schedule id not found: {schedule_id}")

    lowered = normalized.lower()
    matches = [item for item in schedules if str(item.get("name", "")).strip().lower() == lowered]
    if not matches:
        raise ValueError(f"schedule name not found: {normalized}")
    if len(matches) > 1:
        raise ValueError(f"multiple schedules share name '{normalized}', please use id")
    return int(matches[0]["id"])
