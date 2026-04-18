from __future__ import annotations

from pydantic import BaseModel


class PlanV1(BaseModel):
    objective: str
    constraints: list[str]
    required_outputs: list[str]
    steps: list[str]
    risk_flags: list[str]
    needs_review: bool
