from __future__ import annotations

import json
import os
from pathlib import Path

from google import genai

from app.utils.json_utils import parse_json_payload


class GeminiClient:
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        system_prompt_path: str,
        fallback_models: list[str] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for live Gemini client mode")
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._fallback_models = list(fallback_models or [])
        self._system_prompt = Path(system_prompt_path).read_text(encoding="utf-8")

    @classmethod
    def for_reviewer(cls) -> "GeminiClient":
        return cls(
            model=os.getenv("GEMINI_MODEL_REVIEWER", "gemini-2.5-pro"),
            api_key=os.getenv("GEMINI_API_KEY"),
            system_prompt_path=os.getenv("REVIEWER_PROMPT_PATH", "app/prompts/reviewer_system.md"),
            fallback_models=_parse_fallback_models(
                os.getenv("GEMINI_MODEL_FALLBACKS", "gemini-2.5-pro,gemini-2.5-flash")
            ),
        )

    @classmethod
    def for_committee_reviewer(cls) -> "GeminiClient":
        return cls(
            model=os.getenv("GEMINI_MODEL_COMMITTEE_REVIEWER", "gemini-2.5-pro"),
            api_key=os.getenv("GEMINI_API_KEY"),
            system_prompt_path=os.getenv("COMMITTEE_REVIEW_PROMPT_PATH", "app/prompts/committee_review_system.md"),
            fallback_models=_parse_fallback_models(
                os.getenv(
                    "GEMINI_MODEL_COMMITTEE_FALLBACKS",
                    os.getenv("GEMINI_MODEL_FALLBACKS", "gemini-2.5-pro,gemini-2.5-flash"),
                )
            ),
        )

    def review(self, plan: dict) -> dict:
        prompt = f"{self._system_prompt}\n\nInput JSON:\n{json.dumps(plan, ensure_ascii=False)}"
        response = self._generate_content(prompt)
        text = response.text or ""
        return parse_json_payload(text)

    def committee_review(self, draft: dict, context: dict) -> dict:
        payload = {"draft": draft, "context": context}
        prompt = f"{self._system_prompt}\n\nInput JSON:\n{json.dumps(payload, ensure_ascii=False)}"
        response = self._generate_content(prompt)
        text = response.text or ""
        return parse_json_payload(text)

    def _generate_content(self, prompt: str):
        candidate_models = [self._model, *self._fallback_models]
        seen: set[str] = set()
        last_exc: Exception | None = None

        for model in candidate_models:
            normalized = str(model).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            try:
                return self._client.models.generate_content(model=normalized, contents=prompt)
            except Exception as exc:
                last_exc = exc
                if _is_model_not_found_error(exc):
                    continue
                raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("no Gemini model candidate available")


def _parse_fallback_models(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _is_model_not_found_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "not_found" in text or ("not found" in text and "model" in text)
