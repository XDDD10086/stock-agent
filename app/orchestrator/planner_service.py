from __future__ import annotations

from typing import Protocol

from app.schemas.plan import PlanV1


class PlannerClientProtocol(Protocol):
    def plan(self, task_input: str) -> dict: ...


class PlannerService:
    def __init__(self, client: PlannerClientProtocol) -> None:
        self._client = client

    def generate_plan(self, task_input: str) -> PlanV1:
        payload = self._client.plan(task_input)
        return PlanV1.model_validate(payload)
