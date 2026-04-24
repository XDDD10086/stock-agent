from __future__ import annotations

import json

from app.discord_bridge.state_store import DeliveryStateStore


def test_state_store_persists_and_reloads(tmp_path) -> None:
    path = tmp_path / "state.json"
    store = DeliveryStateStore(str(path))
    store.mark_delivered("task_a")
    store.mark_delivered("task_b")

    assert store.is_delivered("task_a") is True
    assert store.is_delivered("task_missing") is False
    assert path.exists()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["delivered_task_ids"] == ["task_a", "task_b"]

    reloaded = DeliveryStateStore(str(path))
    assert reloaded.is_delivered("task_a") is True
    assert reloaded.is_delivered("task_b") is True


def test_state_store_recovers_from_corrupt_file(tmp_path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not-json", encoding="utf-8")

    store = DeliveryStateStore(str(path))
    assert store.is_delivered("task_x") is False

    store.mark_delivered("task_x")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["delivered_task_ids"] == ["task_x"]


def test_state_store_caps_entry_count(tmp_path) -> None:
    path = tmp_path / "state.json"
    store = DeliveryStateStore(str(path), max_entries=2)
    store.mark_delivered("task_a")
    store.mark_delivered("task_b")
    store.mark_delivered("task_c")

    payload = json.loads(path.read_text(encoding="utf-8"))
    # Store keeps the lexical tail when trimming.
    assert payload["delivered_task_ids"] == ["task_b", "task_c"]
