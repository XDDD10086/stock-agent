from __future__ import annotations

from app.discord_bridge.formatter import build_final_result_embed, truncate_text


def test_truncate_text_keeps_boundaries():
    assert truncate_text("abc", 10) == "abc"
    assert truncate_text("abcdefghij", 10) == "abcdefghij"
    assert truncate_text("abcdefghijk", 10).endswith("...")
    assert len(truncate_text("abcdefghijk", 10)) == 10


def test_build_final_result_embed_contains_core_fields_and_truncates_summary():
    payload = {
        "task_id": "task_123",
        "status": "completed",
        "risk_rating": "yellow",
        "summary": "x" * 1000,
        "highlights": ["h1", "h2"],
        "failed_step": None,
        "error_message": None,
    }

    embed = build_final_result_embed(payload, title="Manual Run Result")

    assert embed["title"] == "Manual Run Result"
    assert any(item["name"] == "task_id" for item in embed["fields"])
    summary_field = next(item for item in embed["fields"] if item["name"] == "summary")
    assert len(summary_field["value"]) <= 700
