from __future__ import annotations

import pytest

from app.discord_bridge.config import load_bridge_config_from_env


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DISCORD_APPLICATION_ID", "123")
    monkeypatch.setenv("DISCORD_GUILD_ID", "456")
    monkeypatch.setenv("DISCORD_ALLOWED_CHANNEL_IDS", "100,200")
    monkeypatch.setenv("DISCORD_RUN_CHANNEL_IDS", "100")
    monkeypatch.setenv("DISCORD_SCHEDULE_CHANNEL_IDS", "200")
    monkeypatch.setenv("DISCORD_RESULT_CHANNEL_ID", "100")
    monkeypatch.setenv("DISCORD_API_BASE_URL", "http://127.0.0.1:8000")


def test_load_bridge_config_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.delenv("DISCORD_TASK_WATCH_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("DISCORD_TASK_WATCH_LOOKBACK_MINUTES", raising=False)
    monkeypatch.delenv("DISCORD_DELIVERY_STATE_PATH", raising=False)
    monkeypatch.delenv("DISCORD_HTTP_TIMEOUT_SECONDS", raising=False)

    cfg = load_bridge_config_from_env()

    assert cfg.allowed_channel_ids == {100, 200}
    assert cfg.run_channel_ids == {100}
    assert cfg.schedule_channel_ids == {200}
    assert cfg.response_format == "embed"
    assert cfg.longrun_ack is True
    assert cfg.schedule_allow_everyone is False
    assert cfg.cancel_by_name_allowed is True
    assert cfg.task_watch_interval_seconds == 5
    assert cfg.task_watch_lookback_minutes == 180
    assert cfg.delivery_state_path == "./data/discord_bridge_state.json"
    assert cfg.http_timeout_seconds == 30


def test_load_bridge_config_applies_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("DISCORD_RESPONSE_FORMAT", "text")
    monkeypatch.setenv("DISCORD_LONGRUN_ACK", "false")
    monkeypatch.setenv("DISCORD_SCHEDULE_MANAGER_ROLE_IDS", "900,901")
    monkeypatch.setenv("DISCORD_RUN_ROLE_IDS", "800")
    monkeypatch.setenv("DISCORD_ADMIN_USER_IDS", "7000")
    monkeypatch.setenv("DISCORD_SCHEDULE_ALLOW_EVERYONE", "true")
    monkeypatch.setenv("DISCORD_CANCEL_BY_NAME_ALLOWED", "0")
    monkeypatch.setenv("DISCORD_TASK_WATCH_INTERVAL_SECONDS", "7")
    monkeypatch.setenv("DISCORD_TASK_WATCH_LOOKBACK_MINUTES", "90")
    monkeypatch.setenv("DISCORD_DELIVERY_STATE_PATH", "./tmp/state.json")
    monkeypatch.setenv("DISCORD_HTTP_TIMEOUT_SECONDS", "45")

    cfg = load_bridge_config_from_env()

    assert cfg.response_format == "text"
    assert cfg.longrun_ack is False
    assert cfg.schedule_manager_role_ids == {900, 901}
    assert cfg.run_role_ids == {800}
    assert cfg.admin_user_ids == {7000}
    assert cfg.schedule_allow_everyone is True
    assert cfg.cancel_by_name_allowed is False
    assert cfg.task_watch_interval_seconds == 7
    assert cfg.task_watch_lookback_minutes == 90
    assert cfg.delivery_state_path == "./tmp/state.json"
    assert cfg.http_timeout_seconds == 45


def test_load_bridge_config_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "")

    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        load_bridge_config_from_env()
