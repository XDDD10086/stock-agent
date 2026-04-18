import json

from app.providers.gemini_client import GeminiClient
from app.providers.openai_client import OpenAIClient


class _FakeOpenAIResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class _FakeOpenAIResponses:
    def __init__(self, owner) -> None:
        self._owner = owner

    def create(self, **kwargs):
        self._owner.last_request = kwargs
        return _FakeOpenAIResponse('{"ok": true, "source": "openai"}')


class _FakeOpenAI:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.last_request = None
        self.responses = _FakeOpenAIResponses(self)


class _FakeGeminiResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeGeminiModels:
    def __init__(self, owner) -> None:
        self._owner = owner

    def generate_content(self, *, model: str, contents: str):
        self._owner.last_model = model
        self._owner.last_contents = contents
        return _FakeGeminiResponse('{"ok": true, "source": "gemini"}')


class _FakeGeminiClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.last_model = None
        self.last_contents = None
        self.models = _FakeGeminiModels(self)


def test_openai_finalizer_serializes_payload_as_json(monkeypatch, tmp_path):
    prompt_file = tmp_path / "finalizer.md"
    prompt_file.write_text("system prompt", encoding="utf-8")
    monkeypatch.setattr("app.providers.openai_client.OpenAI", _FakeOpenAI)
    client = OpenAIClient(model="fake-model", api_key="k", system_prompt_path=str(prompt_file))

    result = client.finalize({"a": 1}, {"b": 2})

    assert result["ok"] is True
    user_payload = client._client.last_request["input"][1]["content"]
    parsed = json.loads(user_payload)
    assert parsed["plan"] == {"a": 1}
    assert parsed["review"] == {"b": 2}


def test_openai_committee_finalize_serializes_payload_as_json(monkeypatch, tmp_path):
    prompt_file = tmp_path / "committee_finalize.md"
    prompt_file.write_text("committee finalize prompt", encoding="utf-8")
    monkeypatch.setattr("app.providers.openai_client.OpenAI", _FakeOpenAI)
    client = OpenAIClient(model="fake-model", api_key="k", system_prompt_path=str(prompt_file))

    result = client.committee_finalize(
        {"summary": "draft"},
        {"approved": True, "issues": []},
        {"task_input": "scan portfolio"},
    )

    assert result["ok"] is True
    user_payload = client._client.last_request["input"][1]["content"]
    parsed = json.loads(user_payload)
    assert parsed["draft"] == {"summary": "draft"}
    assert parsed["review"] == {"approved": True, "issues": []}
    assert parsed["context"] == {"task_input": "scan portfolio"}


def test_gemini_reviewer_serializes_plan_as_json(monkeypatch, tmp_path):
    prompt_file = tmp_path / "reviewer.md"
    prompt_file.write_text("review prompt", encoding="utf-8")
    monkeypatch.setattr("app.providers.gemini_client.genai.Client", _FakeGeminiClient)
    client = GeminiClient(model="fake-model", api_key="k", system_prompt_path=str(prompt_file))

    result = client.review({"ticker": "AAPL", "steps": ["one"]})

    assert result["ok"] is True
    assert '"ticker": "AAPL"' in client._client.last_contents
    assert "'ticker': 'AAPL'" not in client._client.last_contents


def test_gemini_committee_reviewer_serializes_payload(monkeypatch, tmp_path):
    prompt_file = tmp_path / "committee_review.md"
    prompt_file.write_text("committee review prompt", encoding="utf-8")
    monkeypatch.setattr("app.providers.gemini_client.genai.Client", _FakeGeminiClient)
    client = GeminiClient(model="fake-model", api_key="k", system_prompt_path=str(prompt_file))

    result = client.committee_review({"summary": "draft"}, {"task_input": "AAPL analysis"})

    assert result["ok"] is True
    assert '"summary": "draft"' in client._client.last_contents
    assert '"task_input": "AAPL analysis"' in client._client.last_contents
