from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

from app.utils.json_utils import parse_json_payload


class OpenAIClient:
    def __init__(self, *, model: str, api_key: str | None, system_prompt_path: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for live OpenAI client mode")
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._system_prompt = Path(system_prompt_path).read_text(encoding="utf-8")

    @classmethod
    def for_planner(cls) -> "OpenAIClient":
        return cls(
            model=os.getenv("OPENAI_MODEL_PLANNER", "gpt-5.4"),
            api_key=os.getenv("OPENAI_API_KEY"),
            system_prompt_path=os.getenv("PLANNER_PROMPT_PATH", "app/prompts/planner_system.md"),
        )

    @classmethod
    def for_finalizer(cls) -> "OpenAIClient":
        return cls(
            model=os.getenv("OPENAI_MODEL_FINALIZER", "gpt-5.4"),
            api_key=os.getenv("OPENAI_API_KEY"),
            system_prompt_path=os.getenv("FINALIZER_PROMPT_PATH", "app/prompts/finalizer_system.md"),
        )

    @classmethod
    def for_committee_drafter(cls) -> "OpenAIClient":
        return cls(
            model=os.getenv("OPENAI_MODEL_COMMITTEE_DRAFTER", "gpt-5.4"),
            api_key=os.getenv("OPENAI_API_KEY"),
            system_prompt_path=os.getenv("COMMITTEE_DRAFT_PROMPT_PATH", "app/prompts/committee_draft_system.md"),
        )

    @classmethod
    def for_committee_finalizer(cls) -> "OpenAIClient":
        return cls(
            model=os.getenv("OPENAI_MODEL_COMMITTEE_FINALIZER", "gpt-5.4"),
            api_key=os.getenv("OPENAI_API_KEY"),
            system_prompt_path=os.getenv("COMMITTEE_FINALIZE_PROMPT_PATH", "app/prompts/committee_finalize_system.md"),
        )

    def plan(self, task_input: str) -> dict:
        return self._generate_json(user_input=task_input)

    def finalize(self, plan: dict, review: dict) -> dict:
        payload = {
            "plan": plan,
            "review": review,
        }
        return self._generate_json(user_input=json.dumps(payload, ensure_ascii=False))

    def committee_draft(self, context: dict) -> dict:
        return self._generate_json(user_input=json.dumps(context, ensure_ascii=False))

    def committee_finalize(self, draft: dict, review: dict, context: dict) -> dict:
        payload = {
            "draft": draft,
            "review": review,
            "context": context,
        }
        return self._generate_json(user_input=json.dumps(payload, ensure_ascii=False))

    def _generate_json(self, user_input: str) -> dict:
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.0,
        )
        text = response.output_text or ""
        return parse_json_payload(text)
