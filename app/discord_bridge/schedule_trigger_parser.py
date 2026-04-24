from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
import re
from typing import Any

from app.utils.json_utils import parse_json_payload


WEEKDAY_ALIASES = {
    "mon": "mon",
    "monday": "mon",
    "周一": "mon",
    "星期一": "mon",
    "tue": "tue",
    "tuesday": "tue",
    "周二": "tue",
    "星期二": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "周三": "wed",
    "星期三": "wed",
    "thu": "thu",
    "thursday": "thu",
    "周四": "thu",
    "星期四": "thu",
    "fri": "fri",
    "friday": "fri",
    "周五": "fri",
    "星期五": "fri",
    "sat": "sat",
    "saturday": "sat",
    "周六": "sat",
    "星期六": "sat",
    "sun": "sun",
    "sunday": "sun",
    "周日": "sun",
    "星期日": "sun",
    "星期天": "sun",
    "周天": "sun",
}


@dataclass(frozen=True)
class ParsedScheduleTrigger:
    trigger_type: str
    cron: str | None
    run_at_local: str | None
    time_of_day: str | None
    days_of_week: list[str] | None
    interval_minutes: int | None
    timezone: str

    def model_dump(self) -> dict[str, Any]:
        return {
            "trigger_type": self.trigger_type,
            "cron": self.cron,
            "run_at_local": self.run_at_local,
            "time_of_day": self.time_of_day,
            "days_of_week": self.days_of_week,
            "interval_minutes": self.interval_minutes,
            "timezone": self.timezone,
        }


class ScheduleTriggerParser:
    def __init__(self, *, timezone_default: str, model: str | None = None, api_key: str | None = None) -> None:
        self._timezone_default = timezone_default
        self._model = model or os.getenv("OPENAI_MODEL_SCHEDULE_PARSER", "gpt-5.4")
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._openai_client = self._build_openai_client(self._api_key)

    def parse(self, trigger_text: str) -> ParsedScheduleTrigger:
        text = trigger_text.strip()
        if not text:
            raise ValueError("触发方式不能为空")

        if self._openai_client is not None:
            try:
                payload = self._parse_with_llm(text)
                return self._normalize(payload)
            except Exception:
                # Keep bridge usable even if LLM parser is temporarily unavailable.
                pass

        payload = self._parse_with_fallback(text)
        return self._normalize(payload)

    def _build_openai_client(self, api_key: str | None):
        if not api_key:
            return None
        try:
            from openai import OpenAI

            return OpenAI(api_key=api_key)
        except Exception:
            return None

    def _parse_with_llm(self, trigger_text: str) -> dict[str, Any]:
        assert self._openai_client is not None

        system_prompt = (
            "You convert natural language schedule descriptions into strict JSON for a scheduler API. "
            "Return JSON object only with keys: trigger_type, cron, run_at_local, time_of_day, days_of_week, "
            "interval_minutes, timezone. Allowed trigger_type: cron, once, one-off, daily, weekly, interval. "
            "days_of_week must use mon/tue/wed/thu/fri/sat/sun. "
            f"If timezone is omitted, default to {self._timezone_default}."
        )

        response = self._openai_client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": trigger_text},
            ],
            temperature=0.0,
        )
        return parse_json_payload(response.output_text or "")

    def _parse_with_fallback(self, trigger_text: str) -> dict[str, Any]:
        text = trigger_text.strip()
        lowered = text.lower()

        cron = self._extract_cron(text)
        if cron:
            return {
                "trigger_type": "cron",
                "cron": cron,
                "timezone": self._timezone_default,
            }

        interval = self._extract_interval_minutes(text)
        if interval is not None:
            return {
                "trigger_type": "interval",
                "interval_minutes": interval,
                "timezone": self._timezone_default,
            }

        time_of_day = self._extract_time_of_day(text)
        if any(token in lowered for token in ("weekly", "every week", "每周", "每星期")):
            days = self._extract_weekdays(text)
            if not days:
                raise ValueError("weekly 触发需要指定至少一个星期几，例如 mon,wed,fri")
            if not time_of_day:
                raise ValueError("weekly 触发需要时间，例如 16:00")
            return {
                "trigger_type": "weekly",
                "time_of_day": time_of_day,
                "days_of_week": days,
                "timezone": self._timezone_default,
            }

        if any(token in lowered for token in ("daily", "every day", "每天")):
            if not time_of_day:
                raise ValueError("daily 触发需要时间，例如 09:30")
            return {
                "trigger_type": "daily",
                "time_of_day": time_of_day,
                "timezone": self._timezone_default,
            }

        if any(token in lowered for token in ("once", "one-off", "one off", "一次", "单次")):
            dt = self._extract_datetime(text)
            if not dt:
                raise ValueError("once 触发需要日期时间，例如 2026-04-24 10:00")
            return {
                "trigger_type": "once",
                "run_at_local": dt,
                "timezone": self._timezone_default,
            }

        raise ValueError(
            "无法解析触发方式。示例：every 30 minutes / 每天 09:30 / weekly mon,wed 16:00 / once 2026-04-24 10:00 / cron: 0 9 * * 1-5"
        )

    def _normalize(self, payload: dict[str, Any]) -> ParsedScheduleTrigger:
        trigger_type = str(payload.get("trigger_type", "")).strip().lower()
        trigger_type = {"oneoff": "one-off", "one off": "one-off"}.get(trigger_type, trigger_type)
        if trigger_type not in {"cron", "once", "one-off", "daily", "weekly", "interval"}:
            raise ValueError(f"unsupported trigger_type: {trigger_type}")

        timezone = str(payload.get("timezone") or self._timezone_default).strip() or self._timezone_default

        cron = _normalize_optional_str(payload.get("cron"))
        run_at_local = _normalize_datetime_str(payload.get("run_at_local"))
        time_of_day = _normalize_time_of_day(payload.get("time_of_day"))
        days_of_week = _normalize_days(payload.get("days_of_week"))
        interval_minutes = _normalize_optional_int(payload.get("interval_minutes"))

        return ParsedScheduleTrigger(
            trigger_type=trigger_type,
            cron=cron,
            run_at_local=run_at_local,
            time_of_day=time_of_day,
            days_of_week=days_of_week,
            interval_minutes=interval_minutes,
            timezone=timezone,
        )

    def _extract_cron(self, text: str) -> str | None:
        cron_after_prefix = re.search(r"(?i)cron\s*[:：]\s*([^\n]+)", text)
        if cron_after_prefix:
            candidate = cron_after_prefix.group(1).strip()
            if _looks_like_cron(candidate):
                return candidate
        return None

    def _extract_interval_minutes(self, text: str) -> int | None:
        m = re.search(r"(?i)every\s+(\d+)\s*(minute|minutes|min|hour|hours)", text)
        if m:
            value = int(m.group(1))
            unit = m.group(2).lower()
            if "hour" in unit:
                return value * 60
            return value

        m_cn_min = re.search(r"每\s*(\d+)\s*分钟", text)
        if m_cn_min:
            return int(m_cn_min.group(1))

        m_cn_hr = re.search(r"每\s*(\d+)\s*小时", text)
        if m_cn_hr:
            return int(m_cn_hr.group(1)) * 60

        return None

    def _extract_time_of_day(self, text: str) -> str | None:
        m = re.search(r"\b([01]\d|2[0-3]):([0-5]\d)\b", text)
        if m:
            return f"{m.group(1)}:{m.group(2)}"

        # Chinese pattern: 中午12点 / 下午3点30 / 上午9点
        m_cn = re.search(r"(上午|中午|下午|晚上)?\s*(\d{1,2})\s*点(?:\s*(\d{1,2})\s*分?)?", text)
        if not m_cn:
            return None
        period = (m_cn.group(1) or "").strip()
        hour = int(m_cn.group(2))
        minute = int(m_cn.group(3) or 0)
        if hour > 23 or minute > 59:
            return None

        if period in {"下午", "晚上"} and hour < 12:
            hour += 12
        if period == "中午" and hour < 11:
            hour += 12
        if period == "上午" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"

    def _extract_weekdays(self, text: str) -> list[str]:
        lowered = text.lower()
        found: list[str] = []
        for token, normalized in WEEKDAY_ALIASES.items():
            if re.match(r"^[a-z]+$", token):
                if re.search(rf"\b{re.escape(token)}\b", lowered):
                    if normalized not in found:
                        found.append(normalized)
                continue

            if token in text and normalized not in found:
                found.append(normalized)
        return found

    def _extract_datetime(self, text: str) -> str | None:
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?::\d{2})?\b", text)
        if not m:
            return None
        yyyy_mm_dd = m.group(1)
        hh_mm = m.group(2)
        try:
            datetime.strptime(f"{yyyy_mm_dd}T{hh_mm}", "%Y-%m-%dT%H:%M")
        except ValueError:
            return None
        return f"{yyyy_mm_dd}T{hh_mm}"


def _looks_like_cron(text: str) -> bool:
    parts = text.split()
    return len(parts) == 5


def _normalize_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_datetime_str(value: Any) -> str | None:
    text = _normalize_optional_str(value)
    if text is None:
        return None
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    return text


def _normalize_time_of_day(value: Any) -> str | None:
    text = _normalize_optional_str(value)
    if text is None:
        return None
    m = re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", text)
    if not m:
        raise ValueError("time_of_day must be HH:MM")
    return f"{m.group(1)}:{m.group(2)}"


def _normalize_days(value: Any) -> list[str] | None:
    if value is None:
        return None
    items: list[str]
    if isinstance(value, list):
        items = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        items = [part.strip().lower() for part in str(value).split(",") if part.strip()]

    normalized: list[str] = []
    for item in items:
        mapped = WEEKDAY_ALIASES.get(item, item)
        if mapped not in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}:
            continue
        if mapped not in normalized:
            normalized.append(mapped)
    return normalized or None


def _normalize_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    return int(text)
