from __future__ import annotations

import pytest

from app.discord_bridge.schedule_trigger_parser import ScheduleTriggerParser


def _parser() -> ScheduleTriggerParser:
    return ScheduleTriggerParser(timezone_default="America/New_York", api_key="")


def test_parse_interval_from_natural_language():
    parser = _parser()
    parsed = parser.parse("every 30 minutes")
    payload = parsed.model_dump()

    assert payload["trigger_type"] == "interval"
    assert payload["interval_minutes"] == 30
    assert payload["timezone"] == "America/New_York"


def test_parse_daily_from_chinese_natural_language():
    parser = _parser()
    parsed = parser.parse("每天 09:30")
    payload = parsed.model_dump()

    assert payload["trigger_type"] == "daily"
    assert payload["time_of_day"] == "09:30"


def test_parse_daily_from_chinese_noon_phrase():
    parser = _parser()
    parsed = parser.parse("每天中午12点一次")
    payload = parsed.model_dump()

    assert payload["trigger_type"] == "daily"
    assert payload["time_of_day"] == "12:00"


def test_parse_weekly_from_natural_language():
    parser = _parser()
    parsed = parser.parse("weekly mon,wed,fri 16:00")
    payload = parsed.model_dump()

    assert payload["trigger_type"] == "weekly"
    assert payload["time_of_day"] == "16:00"
    assert payload["days_of_week"] == ["mon", "wed", "fri"]


def test_parse_once_from_natural_language():
    parser = _parser()
    parsed = parser.parse("once 2026-04-24 10:00")
    payload = parsed.model_dump()

    assert payload["trigger_type"] == "once"
    assert payload["run_at_local"] == "2026-04-24T10:00"


def test_parse_cron_from_natural_language():
    parser = _parser()
    parsed = parser.parse("cron: 0 9 * * 1-5")
    payload = parsed.model_dump()

    assert payload["trigger_type"] == "cron"
    assert payload["cron"] == "0 9 * * 1-5"


def test_parse_unknown_trigger_raises_helpful_error():
    parser = _parser()
    with pytest.raises(ValueError) as exc:
        parser.parse("在市场情绪好的时候自动运行")

    assert "无法解析触发方式" in str(exc.value)
