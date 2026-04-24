from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import create_app


class FakeBrowserAdapter:
    def connect(self, cdp_url: str) -> None:
        return None

    def open_chat(self, chat_url: str) -> None:
        return None

    def submit_prompt(self, prompt: str) -> None:
        return None

    def wait_until_completed(self, timeout_seconds: int, poll_interval_seconds: int) -> None:
        return None

    def capture_screenshot(self, output_path: str) -> None:
        with open(output_path, "wb") as f:
            f.write(b"PNG")

    def capture_latest_response_text(self) -> str:
        return (
            "Executive Summary: Scheduled task completed.\n\n"
            "Highlights:\n"
            "- Checkpoint A\n"
            "- Checkpoint B\n"
            "Risk Rating: Yellow\n"
        )

    def capture_page_text(self) -> str:
        return "scheduled fallback page text"

    def close(self) -> None:
        return None


def _client(db_url: str | None = None) -> TestClient:
    if db_url is None:
        db_url = f"sqlite:///./data/test_schedules_{uuid4().hex}.db"
    app = create_app(db_url=db_url, adapter_factory=lambda: FakeBrowserAdapter())
    return TestClient(app)


def test_schedule_crud_flow_for_cron_compat():
    client = _client()

    created = client.post(
        "/schedules",
        json={
            "name": "daily_scan",
            "task_input": "scan daily portfolio",
            "trigger_type": "cron",
            "cron": "0 12 * * *",
            "timezone": "America/New_York",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    schedule_id = payload["id"]
    assert payload["enabled"] is True
    assert payload["trigger_type"] == "cron"

    listed = client.get("/schedules")
    assert listed.status_code == 200
    assert any(item["id"] == schedule_id for item in listed.json()["items"])

    paused = client.post(f"/schedules/{schedule_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["enabled"] is False

    resumed = client.post(f"/schedules/{schedule_id}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["enabled"] is True

    deleted = client.delete(f"/schedules/{schedule_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}


def test_schedule_supports_once_daily_weekly_and_patch_update():
    client = _client()
    run_at_local = (datetime.now().replace(microsecond=0) + timedelta(hours=2)).isoformat()

    once_created = client.post(
        "/schedules",
        json={
            "name": "one_time_scan",
            "task_input": "one-time portfolio check",
            "trigger_type": "once",
            "run_at_local": run_at_local,
            "timezone": "America/New_York",
        },
    )
    assert once_created.status_code == 200
    once_payload = once_created.json()
    assert once_payload["trigger_type"] == "once"
    assert once_payload["run_at_utc"] is not None

    daily_created = client.post(
        "/schedules",
        json={
            "name": "daily_open_scan",
            "task_input": "daily opening scan",
            "trigger_type": "daily",
            "time_of_day": "09:30",
            "timezone": "America/New_York",
        },
    )
    assert daily_created.status_code == 200
    assert daily_created.json()["trigger_type"] == "daily"

    weekly_created = client.post(
        "/schedules",
        json={
            "name": "weekly_scan",
            "task_input": "weekly risk review",
            "trigger_type": "weekly",
            "time_of_day": "16:00",
            "days_of_week": ["mon", "wed", "fri"],
            "timezone": "America/New_York",
        },
    )
    assert weekly_created.status_code == 200
    weekly_payload = weekly_created.json()
    assert weekly_payload["trigger_type"] == "weekly"
    assert weekly_payload["days_of_week"] == ["mon", "wed", "fri"]

    schedule_id = weekly_payload["id"]
    updated = client.patch(
        f"/schedules/{schedule_id}",
        json={
            "trigger_type": "daily",
            "time_of_day": "10:15",
            "enabled": False,
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["trigger_type"] == "daily"
    assert updated_payload["time_of_day"] == "10:15"
    assert updated_payload["enabled"] is False


def test_schedule_supports_one_off_and_interval_trigger_types():
    client = _client()
    run_at_local = (datetime.now().replace(microsecond=0) + timedelta(hours=3)).isoformat()

    one_off_created = client.post(
        "/schedules",
        json={
            "name": "one_off_scan",
            "task_input": "one off portfolio check",
            "trigger_type": "one-off",
            "run_at_local": run_at_local,
            "timezone": "America/New_York",
        },
    )
    assert one_off_created.status_code == 200
    one_off_payload = one_off_created.json()
    assert one_off_payload["trigger_type"] == "one-off"
    assert one_off_payload["run_at_utc"] is not None

    interval_created = client.post(
        "/schedules",
        json={
            "name": "interval_scan",
            "task_input": "interval risk check",
            "trigger_type": "interval",
            "interval_minutes": 30,
            "timezone": "America/New_York",
        },
    )
    assert interval_created.status_code == 200
    interval_payload = interval_created.json()
    assert interval_payload["trigger_type"] == "interval"
    assert interval_payload["interval_minutes"] == 30

    interval_id = interval_payload["id"]
    updated = client.patch(
        f"/schedules/{interval_id}",
        json={
            "trigger_type": "interval",
            "interval_minutes": 45,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["interval_minutes"] == 45


def test_interval_schedule_requires_interval_minutes():
    client = _client()
    created = client.post(
        "/schedules",
        json={
            "name": "invalid_interval",
            "task_input": "invalid interval schedule",
            "trigger_type": "interval",
            "timezone": "America/New_York",
        },
    )
    assert created.status_code == 422


def test_run_once_endpoint_executes_and_returns_final_result():
    client = _client()
    created = client.post(
        "/schedules",
        json={
            "name": "manual_run",
            "task_input": "trigger manual run",
            "trigger_type": "daily",
            "time_of_day": "10:00",
            "timezone": "America/New_York",
        },
    )
    assert created.status_code == 200
    schedule_id = created.json()["id"]

    run_once = client.post(f"/schedules/{schedule_id}/run-once")
    assert run_once.status_code == 200
    payload = run_once.json()
    assert payload["status"] == "completed"
    assert payload["task_id"]
    assert payload["valuecell_raw_response"]
    assert payload["prompt_chain_status"] in {"direct_pass", "revised_once"}
    assert payload["committee_status"] in {"completed", "fallback"}
    if payload["committee_status"] == "completed":
        assert payload["committee_report_json"] is not None
        assert payload["committee_report_markdown"] is not None

    trigger_meta = client.get(f"/tasks/{payload['task_id']}/artifacts/trigger_meta")
    assert trigger_meta.status_code == 200
    trigger_payload = trigger_meta.json()["payload"]
    assert trigger_payload["source"] == "schedule_run_once"
    assert trigger_payload["schedule_id"] == schedule_id


def test_once_schedule_rejects_past_local_time():
    client = _client()
    past_local = (datetime.now(ZoneInfo("America/New_York")) - timedelta(hours=1)).replace(tzinfo=None).isoformat()

    created = client.post(
        "/schedules",
        json={
            "name": "expired_once",
            "task_input": "expired",
            "trigger_type": "once",
            "run_at_local": past_local,
            "timezone": "America/New_York",
        },
    )
    assert created.status_code == 400
