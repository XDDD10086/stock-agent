from __future__ import annotations

import asyncio

import httpx
import pytest

import app.discord_bridge.api_client as api_module
from app.discord_bridge.api_client import ApiClientError, HttpApiClient


def _install_fake_async_client(monkeypatch: pytest.MonkeyPatch, handler):
    class FakeAsyncClient:
        def __init__(self, *, timeout: int):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method: str, url: str, json: dict | None = None):
            return handler(method, url, json, self.timeout)

    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeAsyncClient)


def test_http_api_client_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict | None, int]] = []

    def handler(method: str, url: str, payload: dict | None, timeout: int):
        calls.append((method, url, payload, timeout))
        if method == "POST" and url.endswith("/tasks"):
            return httpx.Response(200, json={"task_id": "task_1"})
        if method == "GET" and url.endswith("/tasks"):
            return httpx.Response(200, json={"items": [{"task_id": "task_1", "status": "created"}]})
        if method == "POST" and url.endswith("/tasks/task_1/run"):
            return httpx.Response(200, json={"task_id": "task_1", "status": "completed"})
        if method == "GET" and url.endswith("/tasks/task_1/result"):
            return httpx.Response(200, json={"task_id": "task_1", "summary": "ok"})
        raise AssertionError(f"unexpected request: {method} {url}")

    _install_fake_async_client(monkeypatch, handler)
    client = HttpApiClient("http://local-api", timeout_seconds=12)

    created = asyncio.run(client.create_task("hello"))
    listed = asyncio.run(client.list_tasks())
    run_result = asyncio.run(client.run_task("task_1"))
    result = asyncio.run(client.get_result("task_1"))

    assert created["task_id"] == "task_1"
    assert listed == [{"task_id": "task_1", "status": "created"}]
    assert run_result["status"] == "completed"
    assert result["summary"] == "ok"
    assert calls[0] == ("POST", "http://local-api/tasks", {"input": "hello"}, 12)


def test_http_api_client_get_artifact_returns_none_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(method: str, url: str, payload: dict | None, timeout: int):
        del method, payload, timeout
        if url.endswith("/artifacts/trigger_meta"):
            return httpx.Response(404, json={"detail": "artifact not found"})
        raise AssertionError(f"unexpected request: {url}")

    _install_fake_async_client(monkeypatch, handler)
    client = HttpApiClient("http://local-api")

    artifact = asyncio.run(client.get_artifact("task_1", "trigger_meta"))
    assert artifact is None


def test_http_api_client_raises_structured_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    sequence = [
        httpx.Response(409, json={"detail": "runner is busy"}),
        httpx.Response(500, content=b"upstream exploded"),
    ]

    def handler(method: str, url: str, payload: dict | None, timeout: int):
        del method, url, payload, timeout
        return sequence.pop(0)

    _install_fake_async_client(monkeypatch, handler)
    client = HttpApiClient("http://local-api")

    with pytest.raises(ApiClientError) as busy_exc:
        asyncio.run(client.run_task("task_1"))
    assert busy_exc.value.status_code == 409
    assert busy_exc.value.detail == "runner is busy"

    with pytest.raises(ApiClientError) as text_exc:
        asyncio.run(client.run_task("task_2"))
    assert text_exc.value.status_code == 500
    assert "upstream exploded" in text_exc.value.detail
