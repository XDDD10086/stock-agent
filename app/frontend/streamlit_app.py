from __future__ import annotations

import json
import os
from datetime import datetime

import requests
import streamlit as st


API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def _post(path: str, payload: dict | None = None) -> dict:
    response = requests.post(f"{API_BASE}{path}", json=payload, timeout=90)
    response.raise_for_status()
    return response.json()


def _get(path: str) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=90)
    response.raise_for_status()
    return response.json()


def _delete(path: str) -> dict:
    response = requests.delete(f"{API_BASE}{path}", timeout=90)
    response.raise_for_status()
    return response.json()


def _patch(path: str, payload: dict | None = None) -> dict:
    response = requests.patch(f"{API_BASE}{path}", json=payload, timeout=90)
    response.raise_for_status()
    return response.json()


def _call(label: str, fn):
    try:
        return fn()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        detail = exc.response.text if exc.response is not None else str(exc)
        st.error(f"{label} failed ({status}): {detail}")
    except Exception as exc:  # pragma: no cover - defensive UI branch
        st.error(f"{label} failed: {exc}")
    return None


def _render_final_result(payload: dict) -> None:
    st.markdown("#### Structured Result")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Status", payload.get("status", "unknown"))
    with c2:
        st.metric("Risk", payload.get("risk_rating", "unknown"))
    with c3:
        st.metric("Prompt Chain", payload.get("prompt_chain_status", "unknown"))

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
    running = len([x for x in task_items if x.get("status") == "running"])
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
            f"<div class='metric-card'><div class='metric-title'>Running</div><div class='metric-value'>{running}</div></div>",
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
            payload = _call("Run task", lambda: _post(f"/tasks/{run_task_id}/run"))
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
    schedule_name = st.text_input("Schedule Name", value="daily_scan")
    schedule_input = st.text_input("Schedule Task Input", value="scan daily portfolio")
    schedule_trigger = st.selectbox("Trigger Type", ["cron", "once", "daily", "weekly"], index=0)
    col_left, col_right = st.columns(2)
    with col_left:
        schedule_timezone = st.text_input("Timezone", value="America/New_York")
        schedule_cron = st.text_input("Cron (for cron)", value="0 12 * * *")
        schedule_time_of_day = st.text_input("Time of Day HH:MM (daily/weekly)", value="09:30")
    with col_right:
        schedule_run_at_local = st.text_input("Run At Local (once, YYYY-MM-DD HH:MM)", value="")
        schedule_days = st.multiselect(
            "Days of Week (weekly)",
            options=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
            default=["mon"],
        )
    if st.button("Create Schedule", use_container_width=True, type="primary"):
        payload_input = {
            "name": schedule_name,
            "task_input": schedule_input,
            "trigger_type": schedule_trigger,
            "timezone": schedule_timezone,
        }
        if schedule_trigger == "cron":
            payload_input["cron"] = schedule_cron
        if schedule_trigger == "once" and schedule_run_at_local.strip():
            payload_input["run_at_local"] = schedule_run_at_local.strip()
        if schedule_trigger in {"daily", "weekly"}:
            payload_input["time_of_day"] = schedule_time_of_day.strip()
        if schedule_trigger == "weekly":
            payload_input["days_of_week"] = schedule_days

        payload = _call(
            "Create schedule",
            lambda: _post("/schedules", payload_input),
        )
        if payload:
            st.success(f"Schedule created: {payload['id']}")
            st.json(payload)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("Manage Schedule")
    schedule_id = st.text_input("Schedule ID")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        if st.button("Pause", use_container_width=True):
            payload = _call("Pause schedule", lambda: _post(f"/schedules/{schedule_id}/pause"))
            if payload:
                st.json(payload)
    with p2:
        if st.button("Resume", use_container_width=True):
            payload = _call("Resume schedule", lambda: _post(f"/schedules/{schedule_id}/resume"))
            if payload:
                st.json(payload)
    with p3:
        if st.button("Delete", use_container_width=True):
            payload = _call("Delete schedule", lambda: _delete(f"/schedules/{schedule_id}"))
            if payload:
                st.json(payload)
    with p4:
        if st.button("Run Once Now", use_container_width=True):
            payload = _call("Run schedule once", lambda: _post(f"/schedules/{schedule_id}/run-once"))
            if payload:
                _render_final_result(payload)

    st.markdown("##### Update Schedule (Partial)")
    update_trigger = st.selectbox("Update Trigger Type (optional)", ["", "cron", "once", "daily", "weekly"], index=0)
    u1, u2 = st.columns(2)
    with u1:
        update_name = st.text_input("Update Name (optional)", value="")
        update_task_input = st.text_input("Update Task Input (optional)", value="")
        update_timezone = st.text_input("Update Timezone (optional)", value="")
        update_cron = st.text_input("Update Cron (optional)", value="")
    with u2:
        update_run_at_local = st.text_input("Update Run At Local (optional)", value="")
        update_time_of_day = st.text_input("Update Time of Day HH:MM (optional)", value="")
        update_days = st.multiselect(
            "Update Days of Week (weekly, optional)",
            options=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
            default=[],
            key="update_days_of_week",
        )
        update_enabled = st.selectbox("Update Enabled (optional)", ["", "true", "false"], index=0)

    if st.button("Apply Update", use_container_width=True):
        update_payload: dict = {}
        if update_name.strip():
            update_payload["name"] = update_name.strip()
        if update_task_input.strip():
            update_payload["task_input"] = update_task_input.strip()
        if update_trigger:
            update_payload["trigger_type"] = update_trigger
        if update_timezone.strip():
            update_payload["timezone"] = update_timezone.strip()
        if update_cron.strip():
            update_payload["cron"] = update_cron.strip()
        if update_run_at_local.strip():
            update_payload["run_at_local"] = update_run_at_local.strip()
        if update_time_of_day.strip():
            update_payload["time_of_day"] = update_time_of_day.strip()
        if update_days:
            update_payload["days_of_week"] = update_days
        if update_enabled == "true":
            update_payload["enabled"] = True
        if update_enabled == "false":
            update_payload["enabled"] = False

        payload = _call("Update schedule", lambda: _patch(f"/schedules/{schedule_id}", update_payload))
        if payload:
            st.success("Schedule updated")
            st.json(payload)
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
