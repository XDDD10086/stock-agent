from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import TaskArtifactRecord, TaskRecord


@dataclass
class TaskDTO:
    task_id: str
    status: str
    input: str
    created_at: datetime
    updated_at: datetime


class TaskService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_task(self, input_text: str) -> TaskDTO:
        now = datetime.now(UTC)
        task = TaskRecord(
            task_id=f"task_{uuid4().hex[:12]}",
            input_text=input_text,
            status="created",
            created_at=now,
            updated_at=now,
        )
        self._db.add(task)
        self._db.commit()
        self._db.refresh(task)
        return _to_dto(task)

    def get_task(self, task_id: str) -> TaskDTO | None:
        record = self._db.query(TaskRecord).filter(TaskRecord.task_id == task_id).one_or_none()
        if record is None:
            return None
        return _to_dto(record)

    def list_tasks(self) -> list[TaskDTO]:
        records = self._db.query(TaskRecord).order_by(TaskRecord.id.desc()).all()
        return [_to_dto(record) for record in records]

    def update_status(self, task_id: str, status: str) -> TaskDTO | None:
        record = self._db.query(TaskRecord).filter(TaskRecord.task_id == task_id).one_or_none()
        if record is None:
            return None
        record.status = status
        record.updated_at = datetime.now(UTC)
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return _to_dto(record)

    def save_artifact(self, task_id: str, artifact_type: str, content: dict) -> None:
        artifact = TaskArtifactRecord(
            task_id=task_id,
            artifact_type=artifact_type,
            content_json=json.dumps(content, ensure_ascii=False),
        )
        self._db.add(artifact)
        self._db.commit()

    def get_latest_artifact(self, task_id: str, artifact_type: str) -> dict | None:
        artifact = (
            self._db.query(TaskArtifactRecord)
            .filter(TaskArtifactRecord.task_id == task_id, TaskArtifactRecord.artifact_type == artifact_type)
            .order_by(TaskArtifactRecord.id.desc())
            .first()
        )
        if artifact is None:
            return None
        return json.loads(artifact.content_json)

    def list_artifact_types(self, task_id: str) -> list[str]:
        rows = (
            self._db.query(TaskArtifactRecord.artifact_type)
            .filter(TaskArtifactRecord.task_id == task_id)
            .distinct()
            .all()
        )
        return sorted([row[0] for row in rows])


def _to_dto(record: TaskRecord) -> TaskDTO:
    return TaskDTO(
        task_id=record.task_id,
        status=record.status,
        input=record.input_text,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
