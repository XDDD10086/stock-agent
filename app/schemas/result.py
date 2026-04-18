from __future__ import annotations

from pydantic import BaseModel, Field


class FinalResult(BaseModel):
    task_id: str
    status: str
    summary: str
    highlights: list[str]
    table: list[dict]
    risk_rating: str
    raw_sources: list[str]
    screenshots: list[str]
    valuecell_raw_response: str | None = None
    prompt_chain_status: str = "direct_pass"
    llm_mode: str = "deterministic"
    llm_fallback_reason: str | None = None
    committee_status: str = "skipped_not_completed"
    committee_summary: str | None = None
    committee_actions: list[dict] = Field(default_factory=list)
    committee_fallback_reason: str | None = None
    committee_report_json: dict | None = None
    committee_report_markdown: str | None = None
    failed_step: str | None = None
    error_message: str | None = None
