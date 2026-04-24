from __future__ import annotations

from app.discord_bridge.config import BridgeConfig
from app.discord_bridge.policy import BridgePolicy, CommandContext, resolve_schedule_target


def _base_config() -> BridgeConfig:
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
        schedule_manager_role_ids={900},
        run_role_ids={800},
        admin_user_ids={7000},
        schedule_allow_everyone=False,
        cancel_by_name_allowed=True,
        task_watch_interval_seconds=5,
        task_watch_lookback_minutes=180,
        delivery_state_path="./data/discord_bridge_state.json",
        http_timeout_seconds=30,
    )


def test_policy_enforces_run_channel_and_role():
    policy = BridgePolicy(_base_config())

    wrong_channel = CommandContext(channel_id=200, user_id=11, role_ids={800})
    ok, reason = policy.authorize_run(wrong_channel)
    assert ok is False
    assert "run channel" in reason.lower()

    missing_role = CommandContext(channel_id=100, user_id=11, role_ids={222})
    ok, reason = policy.authorize_run(missing_role)
    assert ok is False
    assert "role" in reason.lower()

    allowed = CommandContext(channel_id=100, user_id=11, role_ids={800})
    ok, reason = policy.authorize_run(allowed)
    assert ok is True
    assert reason == "ok"


def test_policy_enforces_schedule_channel_and_manager_role_with_admin_override():
    policy = BridgePolicy(_base_config())

    wrong_channel = CommandContext(channel_id=100, user_id=11, role_ids={900})
    ok, reason = policy.authorize_schedule(wrong_channel)
    assert ok is False
    assert "scheduler" in reason.lower()

    non_manager = CommandContext(channel_id=200, user_id=11, role_ids={222})
    ok, reason = policy.authorize_schedule(non_manager)
    assert ok is False
    assert "role" in reason.lower()

    manager = CommandContext(channel_id=200, user_id=11, role_ids={900})
    ok, reason = policy.authorize_schedule(manager)
    assert ok is True

    admin = CommandContext(channel_id=200, user_id=7000, role_ids={222})
    ok, reason = policy.authorize_schedule(admin)
    assert ok is True


def test_resolve_schedule_target_prefers_id_and_handles_name_ambiguity():
    schedules = [
        {"id": 12, "name": "morning"},
        {"id": 18, "name": "night"},
        {"id": 20, "name": "night"},
    ]

    assert resolve_schedule_target("12", schedules) == 12

    try:
        resolve_schedule_target("night", schedules)
    except ValueError as exc:
        assert "multiple" in str(exc).lower()
    else:
        raise AssertionError("expected name ambiguity error")

    assert resolve_schedule_target("morning", schedules) == 12
