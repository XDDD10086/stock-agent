from __future__ import annotations

import pytest

from app.providers.gemini_client import GeminiClient, _is_model_not_found_error, _parse_fallback_models


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, behavior_by_model: dict[str, object]) -> None:
        self._behavior_by_model = behavior_by_model
        self.calls: list[str] = []

    def generate_content(self, *, model: str, contents: str):
        del contents
        self.calls.append(model)
        behavior = self._behavior_by_model[model]
        if isinstance(behavior, Exception):
            raise behavior
        return _FakeResponse(str(behavior))


class _FakeClient:
    def __init__(self, behavior_by_model: dict[str, object]) -> None:
        self.models = _FakeModels(behavior_by_model)


def _build_client(primary_model: str, fallback_models: list[str], behavior_by_model: dict[str, object]) -> GeminiClient:
    client = GeminiClient.__new__(GeminiClient)
    client._client = _FakeClient(behavior_by_model)
    client._model = primary_model
    client._fallback_models = list(fallback_models)
    client._system_prompt = "system prompt"
    return client


def test_review_falls_back_when_primary_model_not_found() -> None:
    client = _build_client(
        "gemini-3.1-pro-preview",
        ["gemini-2.5-pro", "gemini-2.5-flash"],
        {
            "gemini-3.1-pro-preview": RuntimeError("models/gemini-3.1-pro-preview is not found"),
            "gemini-2.5-pro": '{"review":"ok"}',
        },
    )

    payload = client.review({"plan": "demo"})

    assert payload["review"] == "ok"
    assert client._client.models.calls == ["gemini-3.1-pro-preview", "gemini-2.5-pro"]


def test_review_raises_non_model_not_found_error_without_fallback() -> None:
    client = _build_client(
        "gemini-primary",
        ["gemini-fallback"],
        {
            "gemini-primary": RuntimeError("permission denied"),
            "gemini-fallback": '{"review":"should-not-run"}',
        },
    )

    with pytest.raises(RuntimeError, match="permission denied"):
        client.review({"plan": "demo"})

    assert client._client.models.calls == ["gemini-primary"]


def test_fallback_model_parser_and_not_found_detection() -> None:
    assert _parse_fallback_models(" gemini-a,gemini-b ,, ") == ["gemini-a", "gemini-b"]
    assert _parse_fallback_models("") == []
    assert _parse_fallback_models(None) == []

    assert _is_model_not_found_error(RuntimeError("NOT_FOUND: model missing")) is True
    assert _is_model_not_found_error(RuntimeError("models/x is not found")) is True
    assert _is_model_not_found_error(RuntimeError("quota exceeded")) is False
