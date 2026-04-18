from __future__ import annotations

from pydantic import BaseModel


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
    failed_step: str | None = None
    error_message: str | None = None
