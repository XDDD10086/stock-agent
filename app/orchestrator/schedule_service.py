from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models import ScheduleRecord
from app.schemas.schedule import ScheduleCreateRequest, ScheduleUpdateRequest


@dataclass
class ScheduleDTO:
    id: int
    name: str
    task_input: str
    trigger_type: str
    cron: str | None
    run_at_utc: datetime | None
    time_of_day: str | None
    days_of_week: list[str]
    interval_minutes: int | None
    timezone: str
    enabled: bool
    next_run_at: datetime | None
    created_at: datetime


@dataclass
class NormalizedScheduleInput:
    trigger_type: str
    cron: str | None
    run_at_utc: datetime | None
    time_of_day: str | None
    days_of_week: list[str]
    interval_minutes: int | None
    timezone: str


class ScheduleService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_schedule(
        self,
        *,
        name: str,
        task_input: str,
        trigger_type: str,
        cron: str | None,
        run_at_local: datetime | None,
        time_of_day: str | None,
        days_of_week: list[str] | None,
        interval_minutes: int | None,
        timezone: str,
    ) -> ScheduleDTO:
        normalized = _normalize_schedule(
            trigger_type=trigger_type,
            cron=cron,
            run_at_local=run_at_local,
            time_of_day=time_of_day,
            days_of_week=days_of_week,
            interval_minutes=interval_minutes,
            timezone=timezone,
        )
        record = ScheduleRecord(
            name=name,
            task_input=task_input,
            trigger_type=normalized.trigger_type,
            cron=normalized.cron,
            run_at_utc=normalized.run_at_utc,
            time_of_day=normalized.time_of_day,
            days_of_week=_serialize_days(normalized.days_of_week),
            interval_minutes=normalized.interval_minutes,
            timezone=normalized.timezone,
            enabled=True,
            next_run_at=normalized.run_at_utc if normalized.trigger_type in {"once", "one-off"} else None,
            created_at=datetime.now(UTC),
        )
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return _to_dto(record)

    def get_schedule(self, schedule_id: int) -> ScheduleDTO | None:
        record = self._db.query(ScheduleRecord).filter(ScheduleRecord.id == schedule_id).one_or_none()
        if record is None:
            return None
        return _to_dto(record)

    def list_schedules(self) -> list[ScheduleDTO]:
        records = self._db.query(ScheduleRecord).order_by(ScheduleRecord.id.desc()).all()
        return [_to_dto(record) for record in records]

    def update_schedule(self, schedule_id: int, payload: ScheduleUpdateRequest) -> ScheduleDTO | None:
        record = self._db.query(ScheduleRecord).filter(ScheduleRecord.id == schedule_id).one_or_none()
        if record is None:
            return None

        merged = _merge_update_payload(record, payload)
        normalized = _normalize_schedule(
            trigger_type=merged["trigger_type"],
            cron=merged["cron"],
            run_at_local=merged["run_at_local"],
            time_of_day=merged["time_of_day"],
            days_of_week=merged["days_of_week"],
            interval_minutes=merged["interval_minutes"],
            timezone=merged["timezone"],
        )

        if payload.name is not None:
            record.name = payload.name
        if payload.task_input is not None:
            record.task_input = payload.task_input
        if payload.enabled is not None:
            record.enabled = payload.enabled

        record.trigger_type = normalized.trigger_type
        record.cron = normalized.cron
        record.run_at_utc = normalized.run_at_utc
        record.time_of_day = normalized.time_of_day
        record.days_of_week = _serialize_days(normalized.days_of_week)
        record.interval_minutes = normalized.interval_minutes
        record.timezone = normalized.timezone
        record.next_run_at = normalized.run_at_utc if normalized.trigger_type in {"once", "one-off"} else None

        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return _to_dto(record)

    def set_enabled(self, schedule_id: int, enabled: bool) -> ScheduleDTO | None:
        record = self._db.query(ScheduleRecord).filter(ScheduleRecord.id == schedule_id).one_or_none()
        if record is None:
            return None
        record.enabled = enabled
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return _to_dto(record)

    def set_next_run_at(self, schedule_id: int, next_run_at: datetime | None) -> ScheduleDTO | None:
        record = self._db.query(ScheduleRecord).filter(ScheduleRecord.id == schedule_id).one_or_none()
        if record is None:
            return None
        record.next_run_at = next_run_at
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return _to_dto(record)

    def delete_schedule(self, schedule_id: int) -> bool:
        record = self._db.query(ScheduleRecord).filter(ScheduleRecord.id == schedule_id).one_or_none()
        if record is None:
            return False
        self._db.delete(record)
        self._db.commit()
        return True


def _normalize_schedule(
    *,
    trigger_type: str,
    cron: str | None,
    run_at_local: datetime | None,
    time_of_day: str | None,
    days_of_week: list[str] | None,
    interval_minutes: int | None,
    timezone: str,
) -> NormalizedScheduleInput:
    request = ScheduleCreateRequest(
        name="normalized",
        task_input="normalized",
        trigger_type=trigger_type,
        cron=cron,
        run_at_local=run_at_local,
        time_of_day=time_of_day,
        days_of_week=days_of_week,
        interval_minutes=interval_minutes,
        timezone=timezone,
    )
    normalized_cron = request.cron.strip() if request.trigger_type == "cron" and request.cron else ""
    normalized_time_of_day = request.time_of_day if request.trigger_type in {"daily", "weekly"} else None
    normalized_days = list(request.days_of_week or []) if request.trigger_type == "weekly" else []
    normalized_interval_minutes = request.interval_minutes if request.trigger_type == "interval" else None

    run_at_utc = None
    if request.trigger_type in {"once", "one-off"} and request.run_at_local is not None:
        run_at_utc = _to_utc(request.run_at_local, request.timezone)

    return NormalizedScheduleInput(
        trigger_type=request.trigger_type,
        cron=normalized_cron,
        run_at_utc=run_at_utc,
        time_of_day=normalized_time_of_day,
        days_of_week=normalized_days,
        interval_minutes=normalized_interval_minutes,
        timezone=request.timezone,
    )


def _to_utc(local_dt: datetime, timezone: str) -> datetime:
    tz = ZoneInfo(timezone)
    if local_dt.tzinfo is None:
        localized = local_dt.replace(tzinfo=tz)
    else:
        localized = local_dt.astimezone(tz)
    return localized.astimezone(UTC)


def _to_local_naive(utc_dt: datetime, timezone: str) -> datetime:
    localized = utc_dt.astimezone(ZoneInfo(timezone))
    return localized.replace(tzinfo=None)


def _serialize_days(days: list[str]) -> str | None:
    if not days:
        return None
    return ",".join(days)


def _parse_days(serialized: str | None) -> list[str]:
    if not serialized:
        return []
    return [part.strip().lower() for part in serialized.split(",") if part.strip()]


def _merge_update_payload(record: ScheduleRecord, payload: ScheduleUpdateRequest) -> dict:
    run_at_local = None
    if record.run_at_utc is not None:
        run_at_local = _to_local_naive(record.run_at_utc, record.timezone)

    merged = {
        "trigger_type": payload.trigger_type or record.trigger_type,
        "cron": payload.cron if payload.cron is not None else record.cron,
        "run_at_local": payload.run_at_local if payload.run_at_local is not None else run_at_local,
        "time_of_day": payload.time_of_day if payload.time_of_day is not None else record.time_of_day,
        "days_of_week": payload.days_of_week if payload.days_of_week is not None else _parse_days(record.days_of_week),
        "interval_minutes": (
            payload.interval_minutes if payload.interval_minutes is not None else record.interval_minutes
        ),
        "timezone": payload.timezone or record.timezone,
    }
    return merged


def _to_dto(record: ScheduleRecord) -> ScheduleDTO:
    return ScheduleDTO(
        id=record.id,
        name=record.name,
        task_input=record.task_input,
        trigger_type=record.trigger_type,
        cron=record.cron if record.cron not in {"", None} else None,
        run_at_utc=record.run_at_utc,
        time_of_day=record.time_of_day,
        days_of_week=_parse_days(record.days_of_week),
        interval_minutes=record.interval_minutes,
        timezone=record.timezone,
        enabled=record.enabled,
        next_run_at=record.next_run_at,
        created_at=record.created_at,
    )
