from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class DeliveryStateStore:
    def __init__(self, path: str, *, max_entries: int = 5000) -> None:
        self._path = Path(path)
        self._max_entries = max_entries
        self._lock = Lock()
        self._delivered: set[str] | None = None

    def _load(self) -> set[str]:
        if self._delivered is not None:
            return self._delivered
        if not self._path.exists():
            self._delivered = set()
            return self._delivered
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            items = payload.get("delivered_task_ids", [])
            self._delivered = {str(item) for item in items if str(item).strip()}
        except Exception:
            self._delivered = set()
        return self._delivered

    def is_delivered(self, task_id: str) -> bool:
        with self._lock:
            return task_id in self._load()

    def mark_delivered(self, task_id: str) -> None:
        with self._lock:
            delivered = self._load()
            delivered.add(task_id)
            if len(delivered) > self._max_entries:
                # Keep deterministic subset by lexical order; this is enough for dedupe state.
                kept = sorted(delivered)[-self._max_entries :]
                delivered.clear()
                delivered.update(kept)
            self._persist(delivered)

    def _persist(self, delivered: set[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"delivered_task_ids": sorted(delivered)}
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
