from __future__ import annotations

from pydantic import BaseModel


class ReviewV1(BaseModel):
    approved: bool
    missing_items: list[str]
    ambiguities: list[str]
    risk_flags: list[str]
    suggested_changes: list[str]
