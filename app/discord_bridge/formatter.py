from __future__ import annotations

import json


def truncate_text(value: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return "." * max_len
    return value[: max_len - 3] + "..."


def _join_highlights(highlights: list[str], *, max_len: int) -> str:
    if not highlights:
        return "-"
    text = "\n".join(f"- {item}" for item in highlights[:6])
    return truncate_text(text, max_len)


def build_final_result_embed(payload: dict, *, title: str) -> dict:
    status = str(payload.get("status", "unknown"))
    risk = str(payload.get("risk_rating", "unknown"))
    summary = str(payload.get("summary") or "")
    highlights = [str(item) for item in (payload.get("highlights") or [])]
    failed_step = payload.get("failed_step")
    error_message = payload.get("error_message")

    fields = [
        {"name": "task_id", "value": str(payload.get("task_id", "-")), "inline": True},
        {"name": "status", "value": status, "inline": True},
        {"name": "risk_rating", "value": risk, "inline": True},
        {"name": "summary", "value": truncate_text(summary or "-", 700), "inline": False},
        {"name": "highlights", "value": _join_highlights(highlights, max_len=700), "inline": False},
    ]

    if status != "completed":
        fields.append({"name": "failed_step", "value": str(failed_step or "-"), "inline": True})
        fields.append({"name": "error_message", "value": truncate_text(str(error_message or "-"), 700), "inline": False})

    snippet = {
        "task_id": payload.get("task_id"),
        "status": payload.get("status"),
        "risk_rating": payload.get("risk_rating"),
    }
    fields.append(
        {
            "name": "json",
            "value": f"```json\n{truncate_text(json.dumps(snippet, ensure_ascii=False), 680)}\n```",
            "inline": False,
        }
    )

    return {
        "title": title,
        "description": "stock-agent result",
        "color": 0x2E8B57 if status == "completed" else 0xC0392B,
        "fields": fields,
    }


def build_schedule_list_embed(items: list[dict]) -> dict:
    lines: list[str] = []
    for item in items[:20]:
        schedule_id = item.get("id")
        name = item.get("name", "-")
        trigger_type = item.get("trigger_type", "-")
        enabled = item.get("enabled", False)
        lines.append(f"`{schedule_id}` {name} | {trigger_type} | enabled={enabled}")

    description = "\n".join(lines) if lines else "(empty)"
    return {
        "title": "Schedules",
        "description": truncate_text(description, 1800),
        "color": 0x1F8B4C,
        "fields": [],
    }
