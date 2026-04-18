from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreateRequest(BaseModel):
    input: str = Field(min_length=1)


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str
    input: str


class TaskDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    status: str
    input: str
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskDetailResponse]


class TaskArtifactTypesResponse(BaseModel):
    task_id: str
    artifact_types: list[str]


class TaskArtifactResponse(BaseModel):
    task_id: str
    artifact_type: str
    payload: dict
