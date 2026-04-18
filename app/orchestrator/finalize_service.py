from __future__ import annotations

from typing import Protocol

from app.schemas.execution_pack import ExecutionPack
from app.schemas.plan import PlanV1
from app.schemas.review import ReviewV1


class FinalizerClientProtocol(Protocol):
    def finalize(self, plan: dict, review: dict) -> dict: ...


class FinalizeService:
    def __init__(self, client: FinalizerClientProtocol) -> None:
        self._client = client

    def build_execution_pack(self, plan: PlanV1, review: ReviewV1) -> ExecutionPack:
        payload = self._client.finalize(plan.model_dump(), review.model_dump())
        return ExecutionPack.model_validate(payload)
