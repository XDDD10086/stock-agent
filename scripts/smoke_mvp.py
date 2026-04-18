#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass

import httpx


REQUIRED_ARTIFACTS = {
    "plan_v1",
    "review_v1",
    "execution_pack",
    "final_result",
    "runner_diagnostics",
    "orchestration_metrics",
}


@dataclass
class SmokeContext:
    base_url: str
    cdp_url: str
    allow_manual_intervention: bool
    schedule_timeout_seconds: int
    run_schedule: bool


def _pass(message: str) -> None:
    print(f"[PASS] {message}")


def _fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise RuntimeError(message)


def _expect_status_ok(response: httpx.Response, label: str) -> None:
    if response.status_code >= 400:
        _fail(f"{label} returned {response.status_code}: {response.text}")


def _allowed_final_status(ctx: SmokeContext) -> set[str]:
    if ctx.allow_manual_intervention:
        return {"completed", "needs_manual_intervention"}
    return {"completed"}


def check_cdp(ctx: SmokeContext) -> None:
    url = f"{ctx.cdp_url.rstrip('/')}/json/version"
    with httpx.Client(timeout=20) as client:
        response = client.get(url)
        _expect_status_ok(response, "CDP check")
        payload = response.json()
    ws_url = payload.get("webSocketDebuggerUrl")
    if not ws_url:
        _fail("CDP check missing webSocketDebuggerUrl")
    _pass("CDP endpoint reachable and debugger websocket exposed")


def run_task_flow(ctx: SmokeContext) -> str:
    with httpx.Client(timeout=30) as client:
        create = client.post(f"{ctx.base_url}/tasks", json={"input": "MVP smoke: run a short portfolio risk scan"})
        _expect_status_ok(create, "Create task")
        task_id = create.json()["task_id"]
        _pass(f"Task created: {task_id}")

    with httpx.Client(timeout=1200) as client:
        run = client.post(f"{ctx.base_url}/tasks/{task_id}/run")
        _expect_status_ok(run, "Run task")
        run_payload = run.json()

    status = run_payload.get("status")
    if status not in _allowed_final_status(ctx):
        _fail(f"Run returned unexpected status: {status}")
    _pass(f"Task run finished with status={status}")

    with httpx.Client(timeout=20) as client:
        artifacts = client.get(f"{ctx.base_url}/tasks/{task_id}/artifacts")
        _expect_status_ok(artifacts, "List artifacts")
        artifact_types = set(artifacts.json().get("artifact_types", []))

    missing = sorted(REQUIRED_ARTIFACTS - artifact_types)
    if missing:
        _fail(f"Missing required artifacts: {missing}")
    _pass("All required artifacts are present")
    return task_id


def run_schedule_flow(ctx: SmokeContext) -> None:
    with httpx.Client(timeout=20) as client:
        before = client.get(f"{ctx.base_url}/tasks")
        _expect_status_ok(before, "List tasks before schedule")
        known_task_ids = {item["task_id"] for item in before.json().get("items", [])}

        create_schedule = client.post(
            f"{ctx.base_url}/schedules",
            json={
                "name": "mvp_smoke_schedule",
                "task_input": "MVP smoke: scheduler trigger risk scan",
                "trigger_type": "cron",
                "cron": "* * * * *",
                "timezone": "America/New_York",
            },
        )
        _expect_status_ok(create_schedule, "Create schedule")
        schedule_id = create_schedule.json()["id"]
        _pass(f"Schedule created: {schedule_id}")

    created_task_id: str | None = None
    started = time.time()
    try:
        while time.time() - started < ctx.schedule_timeout_seconds:
            with httpx.Client(timeout=20) as client:
                listed = client.get(f"{ctx.base_url}/tasks")
                _expect_status_ok(listed, "Poll tasks for schedule trigger")
                items = listed.json().get("items", [])
            for item in items:
                if item["task_id"] not in known_task_ids:
                    created_task_id = item["task_id"]
                    break
            if created_task_id:
                break
            time.sleep(5)

        if not created_task_id:
            _fail("Scheduler did not create a new task within timeout")
        _pass(f"Scheduler created task: {created_task_id}")

        allowed = _allowed_final_status(ctx)
        final_status: str | None = None
        started_task_wait = time.time()
        while time.time() - started_task_wait < 180:
            with httpx.Client(timeout=20) as client:
                detail = client.get(f"{ctx.base_url}/tasks/{created_task_id}")
                _expect_status_ok(detail, "Poll scheduled task detail")
                payload = detail.json()
            if payload["status"] in {"completed", "needs_manual_intervention"}:
                final_status = payload["status"]
                break
            time.sleep(4)

        if final_status not in allowed:
            _fail(f"Scheduled task ended with unexpected status: {final_status}")
        _pass(f"Scheduled task finalized with status={final_status}")

    finally:
        with httpx.Client(timeout=20) as client:
            deleted = client.delete(f"{ctx.base_url}/schedules/{schedule_id}")
            _expect_status_ok(deleted, "Delete schedule")
        _pass(f"Schedule deleted: {schedule_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end MVP smoke checks against a running API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--skip-cdp-check", action="store_true")
    parser.add_argument("--skip-schedule-check", action="store_true")
    parser.add_argument("--allow-manual-intervention", action="store_true")
    parser.add_argument("--schedule-timeout-seconds", type=int, default=100)
    args = parser.parse_args()

    ctx = SmokeContext(
        base_url=args.base_url.rstrip("/"),
        cdp_url=args.cdp_url.rstrip("/"),
        allow_manual_intervention=args.allow_manual_intervention,
        schedule_timeout_seconds=max(args.schedule_timeout_seconds, 20),
        run_schedule=not args.skip_schedule_check,
    )

    try:
        with httpx.Client(timeout=15) as client:
            health = client.get(f"{ctx.base_url}/health")
            _expect_status_ok(health, "Health check")
            payload = health.json()
            if payload.get("status") != "ok":
                _fail(f"Health payload unexpected: {payload}")
        _pass("API health check passed")

        if not args.skip_cdp_check:
            check_cdp(ctx)

        run_task_flow(ctx)
        if ctx.run_schedule:
            run_schedule_flow(ctx)

        _pass("MVP smoke completed")
        return 0
    except Exception as exc:  # pragma: no cover - script entrypoint safety
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
