from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.orchestrator.execution_service import (
    ExecutionService,
    build_runner_config_from_env,
    release_execution_lock,
    try_acquire_execution_lock,
)
from app.orchestrator.task_service import TaskService
from app.providers.valuecell_runner import BrowserAdapter, ValueCellRunner
from app.schemas.result import FinalResult
from app.schemas.task import (
    TaskArtifactResponse,
    TaskArtifactTypesResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskDetailResponse,
    TaskListResponse,
)


def build_tasks_router(
    session_factory: sessionmaker[Session],
    adapter_factory: Callable[[], BrowserAdapter] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/tasks", tags=["tasks"])

    def _db() -> Session:
        yield from get_db(session_factory)

    @router.post("", response_model=TaskCreateResponse)
    def create_task(payload: TaskCreateRequest, db: Session = Depends(_db)) -> TaskCreateResponse:
        service = TaskService(db)
        task = service.create_task(payload.input)
        return TaskCreateResponse(task_id=task.task_id, status=task.status, input=task.input)

    @router.get("/{task_id}", response_model=TaskDetailResponse)
    def get_task(task_id: str, db: Session = Depends(_db)) -> TaskDetailResponse:
        service = TaskService(db)
        task = service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return TaskDetailResponse(**task.__dict__)

    @router.get("", response_model=TaskListResponse)
    def list_tasks(db: Session = Depends(_db)) -> TaskListResponse:
        service = TaskService(db)
        items = [TaskDetailResponse(**task.__dict__) for task in service.list_tasks()]
        return TaskListResponse(items=items)

    @router.post("/{task_id}/run", response_model=FinalResult)
    def run_task(task_id: str, db: Session = Depends(_db)) -> FinalResult:
        task_service = TaskService(db)
        task = task_service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        if not try_acquire_execution_lock():
            raise HTTPException(status_code=409, detail="runner is busy")

        runner = ValueCellRunner(build_runner_config_from_env())
        executor = ExecutionService(task_service=task_service, runner=runner, adapter_factory=adapter_factory)
        try:
            return executor.run_task(task_id=task_id, task_input=task.input)
        finally:
            release_execution_lock()

    @router.get("/{task_id}/result", response_model=FinalResult)
    def get_result(task_id: str, db: Session = Depends(_db)) -> FinalResult:
        task_service = TaskService(db)
        task = task_service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        runner = ValueCellRunner(build_runner_config_from_env())
        executor = ExecutionService(task_service=task_service, runner=runner, adapter_factory=adapter_factory)
        result = executor.get_result(task_id)
        if result is None:
            raise HTTPException(status_code=404, detail="result not found")
        return result

    @router.get("/{task_id}/artifacts", response_model=TaskArtifactTypesResponse)
    def list_artifacts(task_id: str, db: Session = Depends(_db)) -> TaskArtifactTypesResponse:
        task_service = TaskService(db)
        task = task_service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return TaskArtifactTypesResponse(task_id=task_id, artifact_types=task_service.list_artifact_types(task_id))

    @router.get("/{task_id}/artifacts/{artifact_type}", response_model=TaskArtifactResponse)
    def get_artifact(task_id: str, artifact_type: str, db: Session = Depends(_db)) -> TaskArtifactResponse:
        task_service = TaskService(db)
        task = task_service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")

        artifact = task_service.get_latest_artifact(task_id, artifact_type)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        return TaskArtifactResponse(task_id=task_id, artifact_type=artifact_type, payload=artifact)

    return router
