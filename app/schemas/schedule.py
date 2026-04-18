from __future__ import annotations

from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TriggerType = Literal["cron", "once", "daily", "weekly"]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_VALID_WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
_TIME_OF_DAY_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def normalize_weekdays(days: list[str] | None) -> list[str]:
    if not days:
        return []
    deduped: list[str] = []
    for day in days:
        normalized = day.strip().lower()
        if normalized not in _VALID_WEEKDAYS:
            raise ValueError(f"invalid weekday: {day}")
        if normalized not in deduped:
            deduped.append(normalized)
    return deduped


def validate_time_of_day(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not _TIME_OF_DAY_RE.match(normalized):
        raise ValueError("time_of_day must be HH:MM (24h)")
    return normalized


class ScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    task_input: str = Field(min_length=1)
    trigger_type: TriggerType = "cron"
    cron: str | None = None
    run_at_local: datetime | None = None
    time_of_day: str | None = None
    days_of_week: list[Weekday] | list[str] | None = None
    timezone: str = "America/New_York"

    @model_validator(mode="after")
    def _validate_trigger_shape(self) -> "ScheduleCreateRequest":
        self.time_of_day = validate_time_of_day(self.time_of_day)
        normalized_days = normalize_weekdays(self.days_of_week or [])
        self.days_of_week = normalized_days

        if self.trigger_type == "cron":
            if not self.cron or not self.cron.strip():
                raise ValueError("cron is required when trigger_type=cron")
        elif self.trigger_type == "once":
            if self.run_at_local is None:
                raise ValueError("run_at_local is required when trigger_type=once")
        elif self.trigger_type == "daily":
            if self.time_of_day is None:
                raise ValueError("time_of_day is required when trigger_type=daily")
        elif self.trigger_type == "weekly":
            if self.time_of_day is None:
                raise ValueError("time_of_day is required when trigger_type=weekly")
            if not normalized_days:
                raise ValueError("days_of_week is required when trigger_type=weekly")
        return self


class ScheduleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    task_input: str | None = Field(default=None, min_length=1)
    trigger_type: TriggerType | None = None
    cron: str | None = None
    run_at_local: datetime | None = None
    time_of_day: str | None = None
    days_of_week: list[Weekday] | list[str] | None = None
    timezone: str | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def _validate_optional_fields(self) -> "ScheduleUpdateRequest":
        self.time_of_day = validate_time_of_day(self.time_of_day)
        if self.days_of_week is not None:
            self.days_of_week = normalize_weekdays(self.days_of_week)
        return self


class ScheduleResponse(BaseModel):
    id: int
    name: str
    task_input: str
    trigger_type: TriggerType
    cron: str | None
    run_at_utc: datetime | None
    time_of_day: str | None
    days_of_week: list[str]
    timezone: str
    enabled: bool
    next_run_at: datetime | None
    created_at: datetime


class ScheduleListResponse(BaseModel):
    items: list[ScheduleResponse]
