from __future__ import annotations

import json
import re


def parse_json_payload(text: str) -> dict:
    cleaned = text.strip()
    cleaned = _strip_fenced_block(cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        snippet = _extract_braced_json(cleaned)
        if snippet is None:
            raise ValueError("Unable to parse JSON payload from model output") from None
        parsed = json.loads(snippet)

    if not isinstance(parsed, dict):
        raise ValueError("Parsed model output is not a JSON object")
    return parsed


def _strip_fenced_block(text: str) -> str:
    fence = re.match(r"(?is)^```(?:json)?\s*(.*?)\s*```$", text)
    return fence.group(1).strip() if fence else text


def _extract_braced_json(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]
