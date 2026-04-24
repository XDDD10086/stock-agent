from __future__ import annotations

from app.discord_bridge.api_client import ApiClientError
from app.discord_bridge.runtime import _friendly_run_error_message


def test_friendly_run_error_for_busy_conflict():
    exc = ApiClientError(409, "runner is busy")
    text = _friendly_run_error_message(exc)
    assert "runner is busy" in text
    assert "单会话保护" in text


def test_friendly_run_error_fallback_for_other_errors():
    text = _friendly_run_error_message(RuntimeError("boom"))
    assert text == "Run failed: boom"
