from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

_scheduler: BackgroundScheduler | None = None
_lock = Lock()


def get_scheduler(default_timezone: str) -> BackgroundScheduler:
    global _scheduler
    with _lock:
        if _scheduler is None:
            _scheduler = BackgroundScheduler(timezone=default_timezone)
            _scheduler.start()
        return _scheduler


def upsert_schedule_job(
    *,
    default_timezone: str,
    job_id: str,
    trigger_type: str,
    cron_expr: str | None,
    run_at_utc: datetime | None,
    time_of_day: str | None,
    days_of_week: list[str] | None,
    interval_minutes: int | None,
    timezone: str,
    callback: Callable[..., None],
    kwargs: dict,
) -> datetime | None:
    scheduler = get_scheduler(default_timezone)
    trigger = _build_trigger(
        trigger_type=trigger_type,
        cron_expr=cron_expr,
        run_at_utc=run_at_utc,
        time_of_day=time_of_day,
        days_of_week=days_of_week or [],
        interval_minutes=interval_minutes,
        timezone=timezone,
    )
    job = scheduler.add_job(
        callback,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
        kwargs=kwargs,
        max_instances=1,
        coalesce=True,
    )
    return job.next_run_time


def _build_trigger(
    *,
    trigger_type: str,
    cron_expr: str | None,
    run_at_utc: datetime | None,
    time_of_day: str | None,
    days_of_week: list[str],
    interval_minutes: int | None,
    timezone: str,
):
    if trigger_type == "cron":
        if not cron_expr:
            raise ValueError("cron_expr is required for cron trigger")
        return CronTrigger.from_crontab(cron_expr, timezone=timezone)

    if trigger_type in {"once", "one-off"}:
        if run_at_utc is None:
            raise ValueError("run_at_utc is required for once/one-off trigger")
        if run_at_utc.tzinfo is None:
            run_at_utc = run_at_utc.replace(tzinfo=UTC)
        return DateTrigger(run_date=run_at_utc, timezone="UTC")

    if trigger_type == "interval":
        if interval_minutes is None or interval_minutes <= 0:
            raise ValueError("interval_minutes is required for interval trigger")
        return IntervalTrigger(minutes=interval_minutes, timezone=timezone)

    if time_of_day is None:
        raise ValueError("time_of_day is required for daily/weekly trigger")
    hour_str, minute_str = time_of_day.split(":")
    hour = int(hour_str)
    minute = int(minute_str)

    if trigger_type == "daily":
        return CronTrigger(hour=hour, minute=minute, timezone=timezone)

    if trigger_type == "weekly":
        if not days_of_week:
            raise ValueError("days_of_week is required for weekly trigger")
        return CronTrigger(day_of_week=",".join(days_of_week), hour=hour, minute=minute, timezone=timezone)

    raise ValueError(f"unsupported trigger_type: {trigger_type}")


def pause_job(default_timezone: str, job_id: str) -> None:
    scheduler = get_scheduler(default_timezone)
    scheduler.pause_job(job_id)


def resume_job(default_timezone: str, job_id: str) -> None:
    scheduler = get_scheduler(default_timezone)
    scheduler.resume_job(job_id)


def remove_job(default_timezone: str, job_id: str) -> None:
    scheduler = get_scheduler(default_timezone)
    scheduler.remove_job(job_id)
