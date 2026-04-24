from __future__ import annotations

from typing import Any

from app.discord_bridge.policy import resolve_schedule_target
from app.discord_bridge.schedule_trigger_parser import ScheduleTriggerParser


def build_schedule_create_payload(
    *,
    name: str,
    task_input: str,
    trigger_text: str,
    parser: ScheduleTriggerParser,
) -> dict[str, Any]:
    normalized_name = name.strip()
    normalized_task_input = task_input.strip()
    normalized_trigger = trigger_text.strip()

    if not normalized_name:
        raise ValueError("name is required")
    if not normalized_task_input:
        raise ValueError("task_input is required")
    if not normalized_trigger:
        raise ValueError("trigger is required")

    parsed = parser.parse(normalized_trigger)
    return {
        "name": normalized_name,
        "task_input": normalized_task_input,
        **parsed.model_dump(),
    }


def resolve_schedule_target_for_ui(target: str, schedules: list[dict[str, Any]]) -> int:
    normalized_target = target.strip()
    if not normalized_target:
        raise ValueError("schedule target is required")
    return resolve_schedule_target(normalized_target, schedules)
