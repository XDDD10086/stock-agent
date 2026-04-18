from __future__ import annotations

from pydantic import BaseModel


class BrowserStep(BaseModel):
    action: str
    content: str | None = None


class ExecutionPack(BaseModel):
    target: str
    valuecell_prompt: str
    expected_sections: list[str]
    browser_steps: list[BrowserStep]
    timeout_seconds: int
