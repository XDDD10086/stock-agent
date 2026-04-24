from __future__ import annotations

import pytest

from app.discord_bridge.schedule_trigger_parser import ScheduleTriggerParser
from app.frontend.schedule_ui_helpers import build_schedule_create_payload, resolve_schedule_target_for_ui


def _parser() -> ScheduleTriggerParser:
    return ScheduleTriggerParser(timezone_default="America/New_York", api_key="")


def test_build_schedule_create_payload_parses_natural_language_trigger():
    payload = build_schedule_create_payload(
        name="noon_scan",
        task_input="send hello",
        trigger_text="每天中午12点一次",
        parser=_parser(),
    )
    assert payload["name"] == "noon_scan"
    assert payload["task_input"] == "send hello"
    assert payload["trigger_type"] == "daily"
    assert payload["time_of_day"] == "12:00"


def test_build_schedule_create_payload_requires_name_and_task_input():
    with pytest.raises(ValueError):
        build_schedule_create_payload(
            name="",
            task_input="send hello",
            trigger_text="每天 09:30",
            parser=_parser(),
        )
    with pytest.raises(ValueError):
        build_schedule_create_payload(
            name="daily",
            task_input="",
            trigger_text="每天 09:30",
            parser=_parser(),
        )


def test_resolve_schedule_target_for_ui_supports_id_and_unique_name():
    schedules = [
        {"id": 11, "name": "daily"},
        {"id": 12, "name": "weekly"},
    ]
    assert resolve_schedule_target_for_ui("11", schedules) == 11
    assert resolve_schedule_target_for_ui("weekly", schedules) == 12


def test_resolve_schedule_target_for_ui_rejects_ambiguous_name():
    schedules = [
        {"id": 11, "name": "daily"},
        {"id": 12, "name": "daily"},
    ]
    with pytest.raises(ValueError):
        resolve_schedule_target_for_ui("daily", schedules)
