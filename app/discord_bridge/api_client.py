from __future__ import annotations

import httpx


class ApiClientError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class HttpApiClient:
    def __init__(self, base_url: str, *, timeout_seconds: int = 30) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def create_task(self, prompt: str) -> dict:
        return await self._request("POST", "/tasks", json={"input": prompt})

    async def run_task(self, task_id: str) -> dict:
        return await self._request("POST", f"/tasks/{task_id}/run")

    async def list_tasks(self) -> list[dict]:
        payload = await self._request("GET", "/tasks")
        return list(payload.get("items") or [])

    async def get_result(self, task_id: str) -> dict:
        return await self._request("GET", f"/tasks/{task_id}/result")

    async def get_artifact(self, task_id: str, artifact_type: str) -> dict | None:
        try:
            payload = await self._request("GET", f"/tasks/{task_id}/artifacts/{artifact_type}")
        except ApiClientError as exc:
            if exc.status_code == 404:
                return None
            raise
        return payload.get("payload")

    async def create_schedule(self, payload: dict) -> dict:
        return await self._request("POST", "/schedules", json=payload)

    async def list_schedules(self) -> list[dict]:
        payload = await self._request("GET", "/schedules")
        return list(payload.get("items") or [])

    async def delete_schedule(self, schedule_id: int) -> dict:
        return await self._request("DELETE", f"/schedules/{schedule_id}")

    async def pause_schedule(self, schedule_id: int) -> dict:
        return await self._request("POST", f"/schedules/{schedule_id}/pause")

    async def resume_schedule(self, schedule_id: int) -> dict:
        return await self._request("POST", f"/schedules/{schedule_id}/resume")

    async def run_schedule_once(self, schedule_id: int) -> dict:
        return await self._request("POST", f"/schedules/{schedule_id}/run-once")

    async def _request(self, method: str, path: str, *, json: dict | None = None) -> dict:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(method, url, json=json)

        if response.status_code >= 400:
            detail = response.text
            try:
                parsed = response.json()
                detail = str(parsed.get("detail", detail))
            except Exception:
                pass
            raise ApiClientError(response.status_code, detail)

        data = response.json()
        if not isinstance(data, dict):
            return {"value": data}
        return data
