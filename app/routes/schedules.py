from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.orchestrator.execution_service import (
    ExecutionService,
    build_runner_config_from_env,
    release_execution_lock,
    try_acquire_execution_lock,
)
from app.orchestrator.schedule_service import ScheduleService
from app.orchestrator.task_service import TaskService
from app.providers.valuecell_runner import BrowserAdapter, ValueCellRunner
from app.scheduler.apscheduler_setup import remove_job, upsert_schedule_job
from app.schemas.result import FinalResult
from app.schemas.schedule import (
    ScheduleCreateRequest,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdateRequest,
)


def build_schedules_router(
    session_factory: sessionmaker[Session],
    *,
    enable_scheduler: bool,
    adapter_factory: Callable[[], BrowserAdapter] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/schedules", tags=["schedules"])
    default_tz = os.getenv("TIMEZONE", "America/New_York")
    runner_config = build_runner_config_from_env()

    def _db() -> Session:
        yield from get_db(session_factory)

    def _job_id(schedule_id: int) -> str:
        return f"schedule_{schedule_id}"

    def _run_scheduled_task(task_input: str, schedule_id: int, schedule_name: str) -> None:
        if not try_acquire_execution_lock():
            return
        db = session_factory()
        try:
            task_service = TaskService(db)
            task = task_service.create_task(task_input)
            task_service.save_artifact(
                task.task_id,
                "trigger_meta",
                {
                    "source": "schedule",
                    "schedule_id": schedule_id,
                    "schedule_name": schedule_name,
                    "triggered_at_utc": datetime.now(UTC).isoformat(),
                },
            )
            runner = ValueCellRunner(runner_config)
            ExecutionService(task_service=task_service, runner=runner, adapter_factory=adapter_factory).run_task(
                task.task_id, task.input
            )
        finally:
            release_execution_lock()
            db.close()

    def _ensure_once_time_is_future(dto: ScheduleResponse) -> None:
        if dto.trigger_type not in {"once", "one-off"}:
            return
        if dto.run_at_utc is None:
            raise HTTPException(status_code=400, detail="once/one-off schedule requires run_at_utc")
        run_at_utc = dto.run_at_utc
        if run_at_utc.tzinfo is None:
            run_at_utc = run_at_utc.replace(tzinfo=UTC)
        if run_at_utc <= datetime.now(UTC):
            raise HTTPException(status_code=400, detail="once/one-off schedule run_at_local must be in the future")

    def _sync_scheduler_job(service: ScheduleService, dto: ScheduleResponse) -> ScheduleResponse:
        if not enable_scheduler:
            return dto
        if not dto.enabled:
            try:
                remove_job(default_tz, _job_id(dto.id))
            except Exception:
                pass
            updated = service.set_next_run_at(dto.id, None)
            return ScheduleResponse(**(updated.__dict__ if updated else dto.model_dump()))

        next_run_at = upsert_schedule_job(
            default_timezone=default_tz,
            job_id=_job_id(dto.id),
            trigger_type=dto.trigger_type,
            cron_expr=dto.cron,
            run_at_utc=dto.run_at_utc,
            time_of_day=dto.time_of_day,
            days_of_week=dto.days_of_week,
            interval_minutes=dto.interval_minutes,
            timezone=dto.timezone,
            callback=_run_scheduled_task,
            kwargs={"task_input": dto.task_input, "schedule_id": dto.id, "schedule_name": dto.name},
        )
        updated = service.set_next_run_at(dto.id, next_run_at)
        return ScheduleResponse(**(updated.__dict__ if updated else dto.model_dump()))

    @router.post("", response_model=ScheduleResponse)
    def create_schedule(payload: ScheduleCreateRequest, db: Session = Depends(_db)) -> ScheduleResponse:
        service = ScheduleService(db)
        try:
            dto = service.create_schedule(
                name=payload.name,
                task_input=payload.task_input,
                trigger_type=payload.trigger_type,
                cron=payload.cron,
                run_at_local=payload.run_at_local,
                time_of_day=payload.time_of_day,
                days_of_week=list(payload.days_of_week or []),
                interval_minutes=payload.interval_minutes,
                timezone=payload.timezone,
            )
            response = ScheduleResponse(**dto.__dict__)
            _ensure_once_time_is_future(response)
            return _sync_scheduler_job(service, response)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid schedule: {exc}") from exc

    @router.get("", response_model=ScheduleListResponse)
    def list_schedules(db: Session = Depends(_db)) -> ScheduleListResponse:
        service = ScheduleService(db)
        items = [ScheduleResponse(**item.__dict__) for item in service.list_schedules()]
        return ScheduleListResponse(items=items)

    @router.patch("/{schedule_id}", response_model=ScheduleResponse)
    def update_schedule(schedule_id: int, payload: ScheduleUpdateRequest, db: Session = Depends(_db)) -> ScheduleResponse:
        service = ScheduleService(db)
        try:
            dto = service.update_schedule(schedule_id, payload)
            if dto is None:
                raise HTTPException(status_code=404, detail="schedule not found")
            response = ScheduleResponse(**dto.__dict__)
            _ensure_once_time_is_future(response)
            return _sync_scheduler_job(service, response)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid schedule: {exc}") from exc

    @router.post("/{schedule_id}/pause", response_model=ScheduleResponse)
    def pause_schedule(schedule_id: int, db: Session = Depends(_db)) -> ScheduleResponse:
        service = ScheduleService(db)
        dto = service.set_enabled(schedule_id, False)
        if dto is None:
            raise HTTPException(status_code=404, detail="schedule not found")
        if enable_scheduler:
            try:
                remove_job(default_tz, _job_id(schedule_id))
            except Exception:
                pass
        dto = service.set_next_run_at(schedule_id, None) or dto
        return ScheduleResponse(**dto.__dict__)

    @router.post("/{schedule_id}/resume", response_model=ScheduleResponse)
    def resume_schedule(schedule_id: int, db: Session = Depends(_db)) -> ScheduleResponse:
        service = ScheduleService(db)
        dto = service.set_enabled(schedule_id, True)
        if dto is None:
            raise HTTPException(status_code=404, detail="schedule not found")
        response = ScheduleResponse(**dto.__dict__)
        _ensure_once_time_is_future(response)
        try:
            return _sync_scheduler_job(service, response)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid schedule: {exc}") from exc

    @router.post("/{schedule_id}/run-once", response_model=FinalResult)
    def run_schedule_once(schedule_id: int, db: Session = Depends(_db)) -> FinalResult:
        service = ScheduleService(db)
        schedule = service.get_schedule(schedule_id)
        if schedule is None:
            raise HTTPException(status_code=404, detail="schedule not found")
        if not try_acquire_execution_lock():
            raise HTTPException(status_code=409, detail="runner is busy")

        task_service = TaskService(db)
        task = task_service.create_task(schedule.task_input)
        task_service.save_artifact(
            task.task_id,
            "trigger_meta",
            {
                "source": "schedule_run_once",
                "schedule_id": schedule.id,
                "schedule_name": schedule.name,
                "triggered_at_utc": datetime.now(UTC).isoformat(),
            },
        )
        runner = ValueCellRunner(runner_config)
        executor = ExecutionService(task_service=task_service, runner=runner, adapter_factory=adapter_factory)
        try:
            return executor.run_task(task_id=task.task_id, task_input=task.input)
        finally:
            release_execution_lock()

    @router.delete("/{schedule_id}")
    def delete_schedule(schedule_id: int, db: Session = Depends(_db)) -> dict[str, bool]:
        service = ScheduleService(db)
        deleted = service.delete_schedule(schedule_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="schedule not found")
        if enable_scheduler:
            try:
                remove_job(default_tz, _job_id(schedule_id))
            except Exception:
                pass
        return {"deleted": True}

    return router
