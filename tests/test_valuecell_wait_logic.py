import pytest

from app.providers.valuecell_runner import PlaywrightCdpAdapter


class FakePage:
    def __init__(self) -> None:
        self.selector_calls: list[tuple[str, int]] = []
        self.timeout_calls: list[int] = []

    def wait_for_selector(self, selector: str, timeout: int) -> None:
        self.selector_calls.append((selector, timeout))

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.timeout_calls.append(timeout_ms)


class FakeClock:
    def __init__(self, start: float = 0.0, step: float = 0.2) -> None:
        self._value = start - step
        self._step = step

    def __call__(self) -> float:
        self._value += self._step
        return self._value


def _adapter_with_page() -> tuple[PlaywrightCdpAdapter, FakePage]:
    adapter = PlaywrightCdpAdapter()
    page = FakePage()
    adapter._page = page
    return adapter, page


def test_wait_until_completed_requires_stable_meaningful_response(monkeypatch):
    adapter, page = _adapter_with_page()
    samples = iter(
        [
            "Generating response...",
            "Executive Summary: revenue stabilized and drawdown risk is moderate.",
            "Executive Summary: revenue stabilized and drawdown risk is moderate.",
        ]
    )
    monkeypatch.setattr("app.providers.valuecell_runner.monotonic", FakeClock(step=0.2))
    monkeypatch.setattr(adapter, "_extract_latest_assistant_text", lambda: next(samples))

    adapter.wait_until_completed(timeout_seconds=5, poll_interval_seconds=1)

    assert page.selector_calls
    assert page.timeout_calls == [1000, 1000]


def test_wait_until_completed_times_out_on_loading_only_text(monkeypatch):
    adapter, _ = _adapter_with_page()
    monkeypatch.setattr("app.providers.valuecell_runner.monotonic", FakeClock(step=0.6))
    monkeypatch.setattr(adapter, "_extract_latest_assistant_text", lambda: "Typing...")

    with pytest.raises(RuntimeError, match="Timed out waiting for ValueCell response completion"):
        adapter.wait_until_completed(timeout_seconds=1, poll_interval_seconds=1)
