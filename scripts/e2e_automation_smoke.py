#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import time

import requests


def _request(method: str, base_url: str, path: str, *, payload: dict | None = None, timeout: int = 30) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    response = requests.request(method, url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def run_smoke(base_url: str, *, timeout: int) -> None:
    health = _request("GET", base_url, "/health", timeout=timeout)
    print(f"[ok] health: {health}")

    ts = int(time.time())
    task = _request("POST", base_url, "/tasks", payload={"input": f"automation smoke run {ts}"}, timeout=timeout)
    task_id = str(task["task_id"])
    print(f"[ok] created task: {task_id}")

    run_result = _request("POST", base_url, f"/tasks/{task_id}/run", timeout=max(timeout, 120))
    print(f"[ok] ran task: status={run_result.get('status')} risk={run_result.get('risk_rating')}")

    schedule_name = f"automation_smoke_{ts}"
    schedule = _request(
        "POST",
        base_url,
        "/schedules",
        payload={
            "name": schedule_name,
            "task_input": "automation smoke schedule",
            "trigger_type": "daily",
            "time_of_day": "09:30",
            "timezone": "America/New_York",
        },
        timeout=timeout,
    )
    schedule_id = int(schedule["id"])
    print(f"[ok] created schedule: id={schedule_id}")

    schedules = _request("GET", base_url, "/schedules", timeout=timeout).get("items", [])
    if not any(int(item.get("id", -1)) == schedule_id for item in schedules):
        raise RuntimeError("new schedule not found in list endpoint")
    print("[ok] listed schedule")

    paused = _request("POST", base_url, f"/schedules/{schedule_id}/pause", timeout=timeout)
    if paused.get("enabled") is not False:
        raise RuntimeError("pause did not set enabled=false")
    print("[ok] paused schedule")

    resumed = _request("POST", base_url, f"/schedules/{schedule_id}/resume", timeout=timeout)
    if resumed.get("enabled") is not True:
        raise RuntimeError("resume did not set enabled=true")
    print("[ok] resumed schedule")

    run_once = _request("POST", base_url, f"/schedules/{schedule_id}/run-once", timeout=max(timeout, 120))
    run_once_task_id = str(run_once.get("task_id") or "")
    if not run_once_task_id:
        raise RuntimeError("run-once missing task_id")
    print(f"[ok] run-once completed: task_id={run_once_task_id} status={run_once.get('status')}")

    trigger_meta = _request("GET", base_url, f"/tasks/{run_once_task_id}/artifacts/trigger_meta", timeout=timeout).get(
        "payload", {}
    )
    if int(trigger_meta.get("schedule_id", -1)) != schedule_id:
        raise RuntimeError("trigger_meta schedule_id mismatch")
    print("[ok] verified trigger_meta")

    deleted = _request("DELETE", base_url, f"/schedules/{schedule_id}", timeout=timeout)
    if deleted.get("deleted") is not True:
        raise RuntimeError("delete did not return deleted=true")
    print("[ok] deleted schedule")

    print(f"[done] automation smoke passed at {datetime.now(UTC).isoformat()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run automation E2E smoke against local stock-agent API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")
    args = parser.parse_args()

    run_smoke(args.base_url, timeout=args.timeout)


if __name__ == "__main__":
    main()
