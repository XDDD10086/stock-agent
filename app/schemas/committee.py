from __future__ import annotations

from pydantic import BaseModel, Field


class CommitteeAction(BaseModel):
    action: str
    reason: str


class CommitteeDraftV1(BaseModel):
    summary: str
    actions: list[CommitteeAction] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class CommitteeReviewV1(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
    suggested_changes: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class CommitteeResultV1(BaseModel):
    committee_summary: str
    committee_actions: list[CommitteeAction] = Field(default_factory=list)
    detailed_report: dict = Field(default_factory=dict)
