from __future__ import annotations

from dataclasses import dataclass
import os


def _parse_csv_int_set(value: str | None) -> set[int]:
    if value is None:
        return set()
    result: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        result.add(int(token))
    return result


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class BridgeConfig:
    bot_token: str
    application_id: int
    guild_id: int
    allowed_channel_ids: set[int]
    run_channel_ids: set[int]
    schedule_channel_ids: set[int]
    result_channel_id: int
    api_base_url: str
    response_format: str
    longrun_ack: bool
    schedule_manager_role_ids: set[int]
    run_role_ids: set[int]
    admin_user_ids: set[int]
    schedule_allow_everyone: bool
    cancel_by_name_allowed: bool
    task_watch_interval_seconds: int
    task_watch_lookback_minutes: int
    delivery_state_path: str
    http_timeout_seconds: int


def load_bridge_config_from_env() -> BridgeConfig:
    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("DISCORD_BOT_TOKEN is required")

    application_id = int(os.getenv("DISCORD_APPLICATION_ID", "0"))
    guild_id = int(os.getenv("DISCORD_GUILD_ID", "0"))
    result_channel_id = int(os.getenv("DISCORD_RESULT_CHANNEL_ID", "0"))
    if application_id <= 0:
        raise ValueError("DISCORD_APPLICATION_ID is required")
    if guild_id <= 0:
        raise ValueError("DISCORD_GUILD_ID is required")
    if result_channel_id <= 0:
        raise ValueError("DISCORD_RESULT_CHANNEL_ID is required")

    allowed_channel_ids = _parse_csv_int_set(os.getenv("DISCORD_ALLOWED_CHANNEL_IDS"))
    run_channel_ids = _parse_csv_int_set(os.getenv("DISCORD_RUN_CHANNEL_IDS"))
    schedule_channel_ids = _parse_csv_int_set(os.getenv("DISCORD_SCHEDULE_CHANNEL_IDS"))

    if not allowed_channel_ids:
        raise ValueError("DISCORD_ALLOWED_CHANNEL_IDS is required")
    if not run_channel_ids:
        raise ValueError("DISCORD_RUN_CHANNEL_IDS is required")
    if not schedule_channel_ids:
        raise ValueError("DISCORD_SCHEDULE_CHANNEL_IDS is required")

    api_base_url = os.getenv("DISCORD_API_BASE_URL", "http://127.0.0.1:8000").strip()
    if not api_base_url:
        raise ValueError("DISCORD_API_BASE_URL is required")

    return BridgeConfig(
        bot_token=bot_token,
        application_id=application_id,
        guild_id=guild_id,
        allowed_channel_ids=allowed_channel_ids,
        run_channel_ids=run_channel_ids,
        schedule_channel_ids=schedule_channel_ids,
        result_channel_id=result_channel_id,
        api_base_url=api_base_url,
        response_format=os.getenv("DISCORD_RESPONSE_FORMAT", "embed").strip() or "embed",
        longrun_ack=_parse_bool(os.getenv("DISCORD_LONGRUN_ACK"), default=True),
        schedule_manager_role_ids=_parse_csv_int_set(os.getenv("DISCORD_SCHEDULE_MANAGER_ROLE_IDS")),
        run_role_ids=_parse_csv_int_set(os.getenv("DISCORD_RUN_ROLE_IDS")),
        admin_user_ids=_parse_csv_int_set(os.getenv("DISCORD_ADMIN_USER_IDS")),
        schedule_allow_everyone=_parse_bool(os.getenv("DISCORD_SCHEDULE_ALLOW_EVERYONE"), default=False),
        cancel_by_name_allowed=_parse_bool(os.getenv("DISCORD_CANCEL_BY_NAME_ALLOWED"), default=True),
        task_watch_interval_seconds=int(os.getenv("DISCORD_TASK_WATCH_INTERVAL_SECONDS", "5")),
        task_watch_lookback_minutes=int(os.getenv("DISCORD_TASK_WATCH_LOOKBACK_MINUTES", "180")),
        delivery_state_path=os.getenv("DISCORD_DELIVERY_STATE_PATH", "./data/discord_bridge_state.json").strip(),
        http_timeout_seconds=int(os.getenv("DISCORD_HTTP_TIMEOUT_SECONDS", "30")),
    )
