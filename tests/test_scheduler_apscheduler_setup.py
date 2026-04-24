from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

import app.scheduler.apscheduler_setup as scheduler_module


def test_build_trigger_supports_all_trigger_types() -> None:
    cron = scheduler_module._build_trigger(
        trigger_type="cron",
        cron_expr="0 9 * * 1-5",
        run_at_utc=None,
        time_of_day=None,
        days_of_week=[],
        interval_minutes=None,
        timezone="America/New_York",
    )
    assert isinstance(cron, CronTrigger)

    daily = scheduler_module._build_trigger(
        trigger_type="daily",
        cron_expr=None,
        run_at_utc=None,
        time_of_day="09:30",
        days_of_week=[],
        interval_minutes=None,
        timezone="America/New_York",
    )
    assert isinstance(daily, CronTrigger)

    weekly = scheduler_module._build_trigger(
        trigger_type="weekly",
        cron_expr=None,
        run_at_utc=None,
        time_of_day="16:00",
        days_of_week=["mon", "wed"],
        interval_minutes=None,
        timezone="America/New_York",
    )
    assert isinstance(weekly, CronTrigger)

    interval = scheduler_module._build_trigger(
        trigger_type="interval",
        cron_expr=None,
        run_at_utc=None,
        time_of_day=None,
        days_of_week=[],
        interval_minutes=30,
        timezone="America/New_York",
    )
    assert isinstance(interval, IntervalTrigger)

    once = scheduler_module._build_trigger(
        trigger_type="once",
        cron_expr=None,
        run_at_utc=datetime.now(UTC) + timedelta(minutes=10),
        time_of_day=None,
        days_of_week=[],
        interval_minutes=None,
        timezone="America/New_York",
    )
    assert isinstance(once, DateTrigger)


def test_build_trigger_validates_required_fields() -> None:
    with pytest.raises(ValueError, match="cron_expr"):
        scheduler_module._build_trigger(
            trigger_type="cron",
            cron_expr=None,
            run_at_utc=None,
            time_of_day=None,
            days_of_week=[],
            interval_minutes=None,
            timezone="America/New_York",
        )

    with pytest.raises(ValueError, match="days_of_week"):
        scheduler_module._build_trigger(
            trigger_type="weekly",
            cron_expr=None,
            run_at_utc=None,
            time_of_day="09:30",
            days_of_week=[],
            interval_minutes=None,
            timezone="America/New_York",
        )

    with pytest.raises(ValueError, match="interval_minutes"):
        scheduler_module._build_trigger(
            trigger_type="interval",
            cron_expr=None,
            run_at_utc=None,
            time_of_day=None,
            days_of_week=[],
            interval_minutes=0,
            timezone="America/New_York",
        )

    with pytest.raises(ValueError, match="unsupported"):
        scheduler_module._build_trigger(
            trigger_type="not-supported",
            cron_expr=None,
            run_at_utc=None,
            time_of_day="10:00",
            days_of_week=[],
            interval_minutes=None,
            timezone="America/New_York",
        )


def test_upsert_pause_resume_remove_job() -> None:
    scheduler = BackgroundScheduler(timezone="America/New_York")
    scheduler.start()
    scheduler_module._scheduler = scheduler

    try:
        next_run = scheduler_module.upsert_schedule_job(
            default_timezone="America/New_York",
            job_id="schedule_1",
            trigger_type="interval",
            cron_expr=None,
            run_at_utc=None,
            time_of_day=None,
            days_of_week=[],
            interval_minutes=60,
            timezone="America/New_York",
            callback=lambda **_: None,
            kwargs={},
        )
        assert next_run is not None

        scheduler_module.pause_job("America/New_York", "schedule_1")
        scheduler_module.resume_job("America/New_York", "schedule_1")
        scheduler_module.remove_job("America/New_York", "schedule_1")
        assert scheduler.get_job("schedule_1") is None
    finally:
        scheduler.shutdown(wait=False)
        scheduler_module._scheduler = None
