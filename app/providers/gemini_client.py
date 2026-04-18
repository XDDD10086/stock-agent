from __future__ import annotations

import json
import os
from pathlib import Path

from google import genai

from app.utils.json_utils import parse_json_payload


class GeminiClient:
    def __init__(self, *, model: str, api_key: str | None, system_prompt_path: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for live Gemini client mode")
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._system_prompt = Path(system_prompt_path).read_text(encoding="utf-8")

    @classmethod
    def for_reviewer(cls) -> "GeminiClient":
        return cls(
            model=os.getenv("GEMINI_MODEL_REVIEWER", "gemini-3.1-pro"),
            api_key=os.getenv("GEMINI_API_KEY"),
            system_prompt_path=os.getenv("REVIEWER_PROMPT_PATH", "app/prompts/reviewer_system.md"),
        )

    @classmethod
    def for_committee_reviewer(cls) -> "GeminiClient":
        return cls(
            model=os.getenv("GEMINI_MODEL_COMMITTEE_REVIEWER", "gemini-3.1-pro"),
            api_key=os.getenv("GEMINI_API_KEY"),
            system_prompt_path=os.getenv("COMMITTEE_REVIEW_PROMPT_PATH", "app/prompts/committee_review_system.md"),
        )

    def review(self, plan: dict) -> dict:
        prompt = f"{self._system_prompt}\n\nInput JSON:\n{json.dumps(plan, ensure_ascii=False)}"
        response = self._client.models.generate_content(model=self._model, contents=prompt)
        text = response.text or ""
        return parse_json_payload(text)

    def committee_review(self, draft: dict, context: dict) -> dict:
        payload = {"draft": draft, "context": context}
        prompt = f"{self._system_prompt}\n\nInput JSON:\n{json.dumps(payload, ensure_ascii=False)}"
        response = self._client.models.generate_content(model=self._model, contents=prompt)
        text = response.text or ""
        return parse_json_payload(text)
