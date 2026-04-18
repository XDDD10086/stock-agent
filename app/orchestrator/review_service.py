from __future__ import annotations

from typing import Protocol

from app.schemas.plan import PlanV1
from app.schemas.review import ReviewV1


class ReviewerClientProtocol(Protocol):
    def review(self, plan: dict) -> dict: ...


class ReviewService:
    def __init__(self, client: ReviewerClientProtocol) -> None:
        self._client = client

    def review_plan(self, plan: PlanV1) -> ReviewV1:
        payload = self._client.review(plan.model_dump())
        return ReviewV1.model_validate(payload)
