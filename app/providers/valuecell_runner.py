from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Protocol

from app.schemas.execution_pack import ExecutionPack


@dataclass(frozen=True)
class RunnerConfig:
    chat_url: str
    cdp_url: str
    execution_mode: str
    failure_policy: str
    screenshots_dir: str = "./screenshots"
    artifacts_dir: str = "./artifacts"
    poll_interval_seconds: int = 5


@dataclass(frozen=True)
class RunnerOutcome:
    task_id: str
    status: str
    failed_step: str | None
    error_message: str | None
    screenshot_path: str | None
    raw_text_path: str | None
    raw_response_text: str | None = None
    started_at_utc: str | None = None
    ended_at_utc: str | None = None
    duration_seconds: float | None = None
    step_history: list[dict] | None = None


_GENERATION_IN_PROGRESS_MARKERS = (
    "thinking",
    "typing",
    "generating",
    "loading",
    "processing",
    "analyzing",
    "思考中",
    "正在思考",
    "生成中",
    "正在生成",
    "请稍候",
    "请稍等",
)

_TRIVIAL_RESPONSES = {
    "ok",
    "okay",
    "done",
    "yes",
    "no",
    "好的",
    "收到",
}


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def is_generation_in_progress(text: str) -> bool:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in _GENERATION_IN_PROGRESS_MARKERS)


def has_meaningful_response(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if normalized.lower() in _TRIVIAL_RESPONSES:
        return False
    if is_generation_in_progress(normalized):
        return False

    # Heuristic: require enough semantic signal to avoid treating placeholder
    # tokens like "ok" or short loading echoes as final output.
    if len(normalized) < 12:
        return False

    alnum_count = sum(1 for char in normalized if char.isalnum())
    return alnum_count >= 8


class BrowserAdapter(Protocol):
    def connect(self, cdp_url: str) -> None: ...

    def open_chat(self, chat_url: str) -> None: ...

    def submit_prompt(self, prompt: str) -> None: ...

    def wait_until_completed(self, timeout_seconds: int, poll_interval_seconds: int) -> None: ...

    def capture_screenshot(self, output_path: str) -> None: ...

    def capture_latest_response_text(self) -> str: ...

    def capture_page_text(self) -> str: ...

    def close(self) -> None: ...


class ValueCellRunner:
    def __init__(self, config: RunnerConfig) -> None:
        self._config = config

    def preflight_check(self) -> tuple[bool, str]:
        if self._config.execution_mode != "attach_existing":
            return False, "execution_mode must be attach_existing"
        if not self._config.chat_url:
            return False, "chat_url is required"
        if not self._config.cdp_url:
            return False, "cdp_url is required"
        if self._config.failure_policy != "manual_intervention":
            return False, "failure_policy must be manual_intervention"
        return True, "ok"

    def build_submission_payload(self, task_id: str, execution_pack: ExecutionPack) -> dict:
        return {
            "task_id": task_id,
            "chat_url": self._config.chat_url,
            "prompt": execution_pack.valuecell_prompt,
            "target": execution_pack.target,
            "expected_sections": execution_pack.expected_sections,
            "timeout_seconds": execution_pack.timeout_seconds,
        }

    def execute(self, task_id: str, execution_pack: ExecutionPack, adapter: BrowserAdapter | None = None) -> RunnerOutcome:
        ok, reason = self.preflight_check()
        started_at = datetime.now(UTC)
        step_history: list[dict] = []

        def mark_step(step: str) -> None:
            step_history.append(
                {
                    "step": step,
                    "at_utc": datetime.now(UTC).isoformat(),
                }
            )

        if not ok:
            ended_at = datetime.now(UTC)
            return RunnerOutcome(
                task_id=task_id,
                status="needs_manual_intervention",
                failed_step="preflight_check",
                error_message=reason,
                screenshot_path=None,
                raw_text_path=None,
                started_at_utc=started_at.isoformat(),
                ended_at_utc=ended_at.isoformat(),
                duration_seconds=round((ended_at - started_at).total_seconds(), 3),
                step_history=step_history,
            )

        resolved_adapter: BrowserAdapter = adapter or PlaywrightCdpAdapter()
        failed_step = "connect"
        screenshot_path = self._build_screenshot_path(task_id, suffix="failed")
        raw_text_path: str | None = None
        raw_response_text: str | None = None

        try:
            mark_step("connect")
            resolved_adapter.connect(self._config.cdp_url)
            failed_step = "open_chat"
            mark_step("open_chat")
            resolved_adapter.open_chat(self._config.chat_url)

            failed_step = "submit_prompt"
            mark_step("submit_prompt")
            resolved_adapter.submit_prompt(execution_pack.valuecell_prompt)

            failed_step = "wait_until_completed"
            mark_step("wait_until_completed")
            resolved_adapter.wait_until_completed(execution_pack.timeout_seconds, self._config.poll_interval_seconds)

            failed_step = "capture_screenshot"
            mark_step("capture_screenshot")
            screenshot_path = self._build_screenshot_path(task_id, suffix="completed")
            resolved_adapter.capture_screenshot(screenshot_path)

            failed_step = "capture_latest_response_text"
            mark_step("capture_latest_response_text")
            raw_response_text = resolved_adapter.capture_latest_response_text()
            if not raw_response_text:
                failed_step = "capture_page_text_fallback"
                mark_step("capture_page_text_fallback")
                raw_response_text = resolved_adapter.capture_page_text()

            failed_step = "persist_raw_response"
            mark_step("persist_raw_response")
            raw_text_path = self._build_artifact_path(task_id)
            Path(raw_text_path).write_text(raw_response_text, encoding="utf-8")
            ended_at = datetime.now(UTC)

            return RunnerOutcome(
                task_id=task_id,
                status="completed",
                failed_step=None,
                error_message=None,
                screenshot_path=screenshot_path,
                raw_text_path=raw_text_path,
                raw_response_text=raw_response_text,
                started_at_utc=started_at.isoformat(),
                ended_at_utc=ended_at.isoformat(),
                duration_seconds=round((ended_at - started_at).total_seconds(), 3),
                step_history=step_history,
            )
        except Exception as exc:
            # Best effort screenshot on failure for debugging.
            try:
                resolved_adapter.capture_screenshot(screenshot_path)
            except Exception:
                screenshot_path = None
            ended_at = datetime.now(UTC)

            return RunnerOutcome(
                task_id=task_id,
                status="needs_manual_intervention",
                failed_step=failed_step,
                error_message=str(exc),
                screenshot_path=screenshot_path,
                raw_text_path=raw_text_path,
                raw_response_text=raw_response_text,
                started_at_utc=started_at.isoformat(),
                ended_at_utc=ended_at.isoformat(),
                duration_seconds=round((ended_at - started_at).total_seconds(), 3),
                step_history=step_history,
            )
        finally:
            resolved_adapter.close()

    def _build_screenshot_path(self, task_id: str, suffix: str) -> str:
        root = Path(self._config.screenshots_dir)
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return str(root / f"{task_id}_{suffix}_{stamp}.png")

    def _build_artifact_path(self, task_id: str) -> str:
        root = Path(self._config.artifacts_dir)
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return str(root / f"{task_id}_raw_{stamp}.txt")


class PlaywrightCdpAdapter:
    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None

    def connect(self, cdp_url: str) -> None:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.connect_over_cdp(cdp_url)

        contexts = self._browser.contexts
        if not contexts:
            raise RuntimeError("No browser contexts available in attached session")

        context = contexts[0]
        self._page = context.pages[0] if context.pages else context.new_page()

    def open_chat(self, chat_url: str) -> None:
        self._require_page().goto(chat_url, wait_until="domcontentloaded", timeout=60_000)

    def submit_prompt(self, prompt: str) -> None:
        page = self._require_page()

        textbox_selectors = [
            "textarea",
            "textarea[placeholder*='输入']",
            "textarea[placeholder*='例如']",
            "textarea[placeholder*='Input']",
            "textarea[placeholder*='message']",
            "div[contenteditable='true']",
            "[role='textbox']",
        ]

        # Hydration can lag after domcontentloaded; wait briefly for any text box.
        for _ in range(6):
            if any(page.locator(selector).count() > 0 for selector in textbox_selectors):
                break
            page.wait_for_timeout(500)

        for selector in textbox_selectors:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue

            locator.click()
            # Use keyboard-based edit to trigger framework input listeners consistently.
            page.keyboard.press("Meta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(prompt)
            break
        else:
            raise RuntimeError("Unable to locate chat input element")

        submit_selectors = [
            "button[aria-label='Send message']",
            "button[aria-label*='发送']",
            "button[type='submit']",
            "button:has-text('发送')",
            "button:has-text('Send')",
        ]
        for selector in submit_selectors:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_enabled():
                locator.click()
                return

        # Button may become enabled shortly after input event propagation.
        page.wait_for_timeout(400)
        for selector in submit_selectors:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_enabled():
                locator.click()
                return

        page.keyboard.press("Enter")

    def wait_until_completed(self, timeout_seconds: int, poll_interval_seconds: int) -> None:
        page = self._require_page()
        timeout_ms = max(timeout_seconds, 1) * 1000
        poll_ms = max(poll_interval_seconds, 1) * 1000

        # Wait for chat container, then poll until response after latest user turn is stable.
        page.wait_for_selector("main.main-chat-area", timeout=timeout_ms)
        deadline = monotonic() + max(timeout_seconds, 1)
        last_candidate = ""
        stable_polls = 0

        while monotonic() < deadline:
            candidate = self._extract_latest_assistant_text()
            if not candidate:
                page.wait_for_timeout(poll_ms)
                continue

            # ValueCell completion marker in current UI.
            if "已完成任务" in candidate and len(candidate) >= 30:
                return

            if has_meaningful_response(candidate) and not is_generation_in_progress(candidate):
                if candidate == last_candidate:
                    stable_polls += 1
                else:
                    stable_polls = 0
                if stable_polls >= 1:
                    return
            else:
                stable_polls = 0

            last_candidate = candidate
            page.wait_for_timeout(poll_ms)

        raise RuntimeError("Timed out waiting for ValueCell response completion")

    def capture_screenshot(self, output_path: str) -> None:
        self._require_page().screenshot(path=output_path, full_page=True)

    def capture_latest_response_text(self) -> str:
        return self._extract_latest_assistant_text()

    def capture_page_text(self) -> str:
        page = self._require_page()
        body = page.locator("body").inner_text()
        return body.strip()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._page = None

    def _extract_latest_assistant_text(self) -> str:
        page = self._require_page()
        content = page.evaluate(
            """
            () => {
                const main = document.querySelector("main.main-chat-area");
                if (main) {
                    const sections = Array.from(main.querySelectorAll(":scope > section"));
                    let lastUserIdx = -1;
                    for (let i = 0; i < sections.length; i += 1) {
                        const cls = (sections[i].className || "").toString();
                        if (cls.includes("ml-auto")) {
                            lastUserIdx = i;
                        }
                    }
                    for (let i = sections.length - 1; i > lastUserIdx; i -= 1) {
                        const section = sections[i];
                        const cls = (section.className || "").toString();
                        if (cls.includes("ml-auto")) {
                            continue;
                        }
                        const text = (section.innerText || section.textContent || "").trim();
                        if (text) {
                            return text;
                        }
                    }
                }

                const selectors = [
                    "[data-role='assistant']",
                    ".assistant",
                    ".message.assistant",
                    ".message"
                ];
                for (const selector of selectors) {
                    const nodes = Array.from(document.querySelectorAll(selector));
                    for (let i = nodes.length - 1; i >= 0; i -= 1) {
                        const node = nodes[i];
                        const text = (node.innerText || node.textContent || "").trim();
                        if (text) {
                            return text;
                        }
                    }
                }
                return "";
            }
            """
        )
        return _normalize_text(content or "")

    def _require_page(self):
        if self._page is None:
            raise RuntimeError("Browser adapter is not connected")
        return self._page
