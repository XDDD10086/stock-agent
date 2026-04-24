from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import requests
import streamlit as st

from app.discord_bridge.schedule_trigger_parser import ScheduleTriggerParser
from app.frontend.schedule_ui_helpers import build_schedule_create_payload, resolve_schedule_target_for_ui


API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "90"))
API_RUN_TIMEOUT_SECONDS = int(os.getenv("API_RUN_TIMEOUT_SECONDS", "1800"))


def _post(path: str, payload: dict | None = None, *, timeout: int | None = None) -> dict:
    response = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout or API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _get(path: str) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _delete(path: str) -> dict:
    response = requests.delete(f"{API_BASE}{path}", timeout=API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()

def _call(label: str, fn):
    try:
        return fn()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        detail = exc.response.text if exc.response is not None else str(exc)
        if status == 409 and "runner is busy" in detail.lower():
            st.warning("Runner is busy (single-session guard). Please wait for current run to finish and retry.")
            return None
        st.error(f"{label} failed ({status}): {detail}")
    except Exception as exc:  # pragma: no cover - defensive UI branch
        st.error(f"{label} failed: {exc}")
    return None


@st.cache_resource(show_spinner=False)
def _schedule_trigger_parser() -> ScheduleTriggerParser:
    return ScheduleTriggerParser(timezone_default=os.getenv("TIMEZONE", "America/New_York"))


def _schedule_summary_rows(items: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in items:
        rows.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "trigger": item.get("trigger_type"),
                "enabled": item.get("enabled"),
                "next_run_at_utc": item.get("next_run_at_utc"),
            }
        )
    return rows


def _render_final_result(payload: dict) -> None:
    st.markdown("#### Structured Result")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Status", payload.get("status", "unknown"))
    with c2:
        st.metric("Risk", payload.get("risk_rating", "unknown"))
    with c3:
        st.metric("Prompt Chain", payload.get("prompt_chain_status", "unknown"))
    with c4:
        st.metric("LLM Mode", payload.get("llm_mode", "unknown"))
    with c5:
        st.metric("Committee", payload.get("committee_status", "unknown"))

    fallback_reason = payload.get("llm_fallback_reason")
    if fallback_reason:
        st.warning(f"LLM fallback activated: {fallback_reason}")

    committee_fallback = payload.get("committee_fallback_reason")
    committee_summary = payload.get("committee_summary")
    committee_actions = payload.get("committee_actions") or []
    committee_report_markdown = payload.get("committee_report_markdown")
    committee_report_json = payload.get("committee_report_json")

    st.markdown("#### Committee 建议（易懂版）")
    if committee_summary:
        st.write(committee_summary)
    if committee_actions:
        for idx, item in enumerate(committee_actions, start=1):
            action = item.get("action", "")
            reason = item.get("reason", "")
            st.markdown(f"{idx}. **{action}**")
            if reason:
                st.caption(f"原因：{reason}")
    if committee_fallback:
        st.warning(f"Committee fallback: {committee_fallback}")

    if committee_report_markdown:
        st.markdown("#### Committee 完整执行报告")
        st.markdown(committee_report_markdown)

    if committee_report_json:
        with st.expander("Committee Report JSON", expanded=False):
            st.json(committee_report_json)

    with st.expander("Structured Legacy View", expanded=False):
        st.write(payload.get("summary", ""))
        highlights = payload.get("highlights", [])
        if highlights:
            st.write("Highlights:")
            for item in highlights:
                st.write(f"- {item}")

        table_rows = payload.get("table", [])
        if table_rows:
            st.dataframe(table_rows, use_container_width=True)

    with st.expander("ValueCell Raw Response", expanded=False):
        raw_text = payload.get("valuecell_raw_response") or "(empty)"
        st.text(raw_text)

    with st.expander("Raw JSON", expanded=False):
        st.json(payload)


def _render_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;600&display=swap');

        :root {
          --bg-main: #f5f7f6;
          --bg-card: #ffffff;
          --ink: #142022;
          --muted: #617074;
          --accent: #0f766e;
          --accent-soft: #d9f1ee;
          --border: #dde5e3;
        }

        .stApp {
          background:
            radial-gradient(1200px 500px at 0% -10%, #d7ebe8 0%, transparent 50%),
            radial-gradient(1200px 500px at 100% -20%, #ecf3d3 0%, transparent 45%),
            var(--bg-main);
          color: var(--ink);
          font-family: "Space Grotesk", "Avenir Next", sans-serif;
        }

        h1, h2, h3, h4 {
          font-family: "Space Grotesk", "Avenir Next", sans-serif !important;
          letter-spacing: 0.01em;
        }

        .metric-card {
          background: var(--bg-card);
          border: 1px solid var(--border);
          border-radius: 14px;
          padding: 14px 16px;
          box-shadow: 0 10px 24px rgba(16, 24, 40, 0.05);
        }

        .metric-title {
          color: var(--muted);
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          margin-bottom: 6px;
        }

        .metric-value {
          color: var(--ink);
          font-weight: 700;
          font-size: 24px;
        }

        .panel {
          background: var(--bg-card);
          border: 1px solid var(--border);
          border-radius: 14px;
          padding: 14px 16px 10px 16px;
          box-shadow: 0 8px 20px rgba(16, 24, 40, 0.04);
          margin-bottom: 12px;
        }

        .tiny {
          font-size: 12px;
          color: var(--muted);
          font-family: "JetBrains Mono", monospace;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_metrics(tasks: dict | None, schedules: dict | None) -> None:
    task_items = tasks.get("items", []) if tasks else []
    schedule_items = schedules.get("items", []) if schedules else []
    running = 0
    stale_running = 0
    busy_floor = datetime.now(UTC) - timedelta(minutes=30)
    for item in task_items:
        if item.get("status") != "running":
            continue
        timestamp = _parse_utc_timestamp(item.get("updated_at") or item.get("created_at"))
        if timestamp is None or timestamp >= busy_floor:
            running += 1
        else:
            stale_running += 1
    created = len([x for x in task_items if x.get("status") == "created"])
    active_schedules = len([x for x in schedule_items if x.get("enabled") is True])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"<div class='metric-card'><div class='metric-title'>Total Tasks</div><div class='metric-value'>{len(task_items)}</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='metric-card'><div class='metric-title'>Running (active)</div><div class='metric-value'>{running}</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div class='metric-card'><div class='metric-title'>Created</div><div class='metric-value'>{created}</div></div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"<div class='metric-card'><div class='metric-title'>Active Schedules</div><div class='metric-value'>{active_schedules}</div></div>",
            unsafe_allow_html=True,
        )
    if stale_running > 0:
        st.caption(f"Note: {stale_running} stale running task(s) older than 30 minutes are excluded from active running count.")


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None


def _render_task_tab() -> None:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("Task Runner")
    task_input = st.text_area("Task Input", value="scan daily portfolio risk", height=110)
    if st.button("Create Task", use_container_width=True, type="primary"):
        payload = _call("Create task", lambda: _post("/tasks", {"input": task_input}))
        if payload:
            st.session_state["last_task_id"] = payload["task_id"]
            st.success(f"Task created: {payload['task_id']}")
            st.json(payload)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("Run / Result")
    default_task = st.session_state.get("last_task_id", "")
    run_task_id = st.text_input("Task ID", value=default_task)
    col_run, col_fetch = st.columns(2)
    with col_run:
        if st.button("Run Task", use_container_width=True):
            payload = _call(
                "Run task",
                lambda: _post(f"/tasks/{run_task_id}/run", timeout=API_RUN_TIMEOUT_SECONDS),
            )
            if payload:
                st.success(f"Run status: {payload['status']}")
                _render_final_result(payload)
    with col_fetch:
        if st.button("Fetch Result", use_container_width=True):
            payload = _call("Fetch result", lambda: _get(f"/tasks/{run_task_id}/result"))
            if payload:
                _render_final_result(payload)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("Artifacts")
    artifact_task_id = st.text_input("Artifact Task ID", value=default_task)
    artifact_type = st.text_input("Artifact Type", value="final_result")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("List Artifact Types", use_container_width=True):
            payload = _call("List artifacts", lambda: _get(f"/tasks/{artifact_task_id}/artifacts"))
            if payload:
                st.json(payload)
    with col_b:
        if st.button("Fetch Artifact", use_container_width=True):
            payload = _call(
                "Fetch artifact",
                lambda: _get(f"/tasks/{artifact_task_id}/artifacts/{artifact_type}"),
            )
            if payload:
                st.json(payload)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_schedule_tab() -> None:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("Create Schedule")
    st.caption("只保留 3 个输入框：name、任务描述、触发方式（自然语言，自动解析）。")
    schedule_name = st.text_input("Name", value="daily_scan")
    schedule_input = st.text_area("Task Description", value="scan daily portfolio risk", height=100)
    schedule_trigger = st.text_input(
        "Trigger (Natural Language)",
        value="每天 09:30",
        help="示例：every 30 minutes / 每天中午12点一次 / weekly mon,wed,fri 16:00 / once 2026-04-24 10:00 / cron: 0 9 * * 1-5",
    )
    if st.button("Create Schedule", use_container_width=True, type="primary"):
        try:
            payload_input = build_schedule_create_payload(
                name=schedule_name,
                task_input=schedule_input,
                trigger_text=schedule_trigger,
                parser=_schedule_trigger_parser(),
            )
        except ValueError as exc:
            st.error(f"Create schedule failed: {exc}")
            payload_input = None

        payload = _call("Create schedule", lambda: _post("/schedules", payload_input)) if payload_input else None
        if payload:
            st.success(f"Schedule created: {payload['id']}")
            st.caption(
                f"Parsed as `{payload.get('trigger_type')}` · timezone `{payload.get('timezone')}`"
            )
            st.json(payload)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("Manage Schedule")
    schedules_payload = _call("Fetch schedules", lambda: _get("/schedules"))
    schedules = schedules_payload.get("items", []) if schedules_payload else []
    if schedules:
        st.dataframe(_schedule_summary_rows(schedules), use_container_width=True, hide_index=True)
    else:
        st.info("No schedules yet.")

    target = st.text_input("Schedule Target (ID or name)")
    p1, p2, p3, p4 = st.columns(4)

    def _resolve_target() -> int | None:
        try:
            return resolve_schedule_target_for_ui(target, schedules)
        except ValueError as exc:
            st.error(f"Invalid schedule target: {exc}")
            return None

    with p1:
        if st.button("Pause", use_container_width=True):
            schedule_id = _resolve_target()
            payload = _call("Pause schedule", lambda: _post(f"/schedules/{schedule_id}/pause")) if schedule_id else None
            if payload:
                st.json(payload)
    with p2:
        if st.button("Resume", use_container_width=True):
            schedule_id = _resolve_target()
            payload = _call("Resume schedule", lambda: _post(f"/schedules/{schedule_id}/resume")) if schedule_id else None
            if payload:
                st.json(payload)
    with p3:
        if st.button("Delete", use_container_width=True):
            schedule_id = _resolve_target()
            payload = _call("Delete schedule", lambda: _delete(f"/schedules/{schedule_id}")) if schedule_id else None
            if payload:
                st.json(payload)
    with p4:
        if st.button("Run Once Now", use_container_width=True):
            schedule_id = _resolve_target()
            payload = (
                _call(
                    "Run schedule once",
                    lambda: _post(f"/schedules/{schedule_id}/run-once", timeout=API_RUN_TIMEOUT_SECONDS),
                )
                if schedule_id
                else None
            )
            if payload:
                _render_final_result(payload)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_monitor_tab() -> None:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("Snapshot")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Refresh Tasks", use_container_width=True):
            payload = _call("Fetch tasks", lambda: _get("/tasks"))
            if payload:
                st.json(payload)
    with c2:
        if st.button("Refresh Schedules", use_container_width=True):
            payload = _call("Fetch schedules", lambda: _get("/schedules"))
            if payload:
                st.json(payload)
    with c3:
        if st.button("Check Health", use_container_width=True):
            payload = _call("Health check", lambda: _get("/health"))
            if payload:
                st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        f"<p class='tiny'>API_BASE_URL={API_BASE} · Last refresh at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="Stock Agent Console", layout="wide")
_render_theme()
st.title("Stock Agent Operations Console")
st.caption("Single-browser orchestration workspace for tasks, schedules, and artifact inspection.")

tasks_snapshot = _call("Fetch tasks snapshot", lambda: _get("/tasks"))
schedules_snapshot = _call("Fetch schedules snapshot", lambda: _get("/schedules"))
_status_metrics(tasks_snapshot, schedules_snapshot)

tab_task, tab_schedule, tab_monitor = st.tabs(["Task Studio", "Schedule Desk", "Monitor"])
with tab_task:
    _render_task_tab()
with tab_schedule:
    _render_schedule_tab()
with tab_monitor:
    _render_monitor_tab()
