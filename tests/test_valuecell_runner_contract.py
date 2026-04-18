from app.providers.valuecell_runner import RunnerConfig, ValueCellRunner
from app.schemas.execution_pack import BrowserStep, ExecutionPack


class FakeAdapter:
    def __init__(self, fail_at: str | None = None) -> None:
        self.fail_at = fail_at
        self.connected = False

    def connect(self, cdp_url: str) -> None:
        if self.fail_at == "connect":
            raise RuntimeError("connect failed")
        self.connected = True

    def open_chat(self, chat_url: str) -> None:
        if self.fail_at == "open_chat":
            raise RuntimeError("open_chat failed")

    def submit_prompt(self, prompt: str) -> None:
        if self.fail_at == "submit_prompt":
            raise RuntimeError("submit_prompt failed")

    def wait_until_completed(self, timeout_seconds: int, poll_interval_seconds: int) -> None:
        if self.fail_at == "wait_until_completed":
            raise RuntimeError("wait timeout")

    def capture_screenshot(self, output_path: str) -> None:
        if self.fail_at == "capture_screenshot":
            raise RuntimeError("screenshot failed")
        with open(output_path, "wb") as f:
            f.write(b"PNG")

    def capture_latest_response_text(self) -> str:
        if self.fail_at == "capture_latest_response_text":
            raise RuntimeError("capture latest response failed")
        return "latest assistant response content"

    def capture_page_text(self) -> str:
        if self.fail_at == "capture_page_text":
            raise RuntimeError("capture text failed")
        return "valuecell response content"

    def close(self) -> None:
        self.connected = False


def test_preflight_requires_attach_existing_mode():
    config = RunnerConfig(
        chat_url="https://valuecell.cn/zh/chat",
        cdp_url="http://127.0.0.1:9222",
        execution_mode="launch_new",
        failure_policy="manual_intervention",
    )
    runner = ValueCellRunner(config=config)

    ok, reason = runner.preflight_check()

    assert ok is False
    assert "attach_existing" in reason


def test_preflight_accepts_valid_attach_existing_config():
    config = RunnerConfig(
        chat_url="https://valuecell.cn/zh/chat",
        cdp_url="http://127.0.0.1:9222",
        execution_mode="attach_existing",
        failure_policy="manual_intervention",
    )
    runner = ValueCellRunner(config=config)

    ok, reason = runner.preflight_check()

    assert ok is True
    assert reason == "ok"


def test_build_submission_payload():
    config = RunnerConfig(
        chat_url="https://valuecell.cn/zh/chat",
        cdp_url="http://127.0.0.1:9222",
        execution_mode="attach_existing",
        failure_policy="manual_intervention",
    )
    runner = ValueCellRunner(config=config)
    execution_pack = ExecutionPack(
        target="valuecell_web",
        valuecell_prompt="scan portfolio risk",
        expected_sections=["summary", "risk_rating"],
        browser_steps=[BrowserStep(action="open_chat"), BrowserStep(action="submit")],
        timeout_seconds=900,
    )

    payload = runner.build_submission_payload(task_id="task_123", execution_pack=execution_pack)

    assert payload["task_id"] == "task_123"
    assert payload["chat_url"] == "https://valuecell.cn/zh/chat"
    assert payload["prompt"] == "scan portfolio risk"


def test_execute_success_writes_artifacts(tmp_path):
    config = RunnerConfig(
        chat_url="https://valuecell.cn/zh/chat",
        cdp_url="http://127.0.0.1:9222",
        execution_mode="attach_existing",
        failure_policy="manual_intervention",
        screenshots_dir=str(tmp_path / "shots"),
        artifacts_dir=str(tmp_path / "artifacts"),
    )
    runner = ValueCellRunner(config=config)
    execution_pack = ExecutionPack(
        target="valuecell_web",
        valuecell_prompt="scan portfolio risk",
        expected_sections=["summary", "risk_rating"],
        browser_steps=[BrowserStep(action="open_chat"), BrowserStep(action="submit")],
        timeout_seconds=900,
    )

    outcome = runner.execute(task_id="task_ok", execution_pack=execution_pack, adapter=FakeAdapter())

    assert outcome.status == "completed"
    assert outcome.failed_step is None
    assert outcome.screenshot_path is not None
    assert outcome.raw_text_path is not None
    assert outcome.raw_response_text == "latest assistant response content"
    assert outcome.duration_seconds is not None
    assert outcome.duration_seconds >= 0
    assert outcome.step_history
    assert outcome.step_history[-1]["step"] == "persist_raw_response"


def test_execute_failure_returns_manual_intervention(tmp_path):
    config = RunnerConfig(
        chat_url="https://valuecell.cn/zh/chat",
        cdp_url="http://127.0.0.1:9222",
        execution_mode="attach_existing",
        failure_policy="manual_intervention",
        screenshots_dir=str(tmp_path / "shots"),
        artifacts_dir=str(tmp_path / "artifacts"),
    )
    runner = ValueCellRunner(config=config)
    execution_pack = ExecutionPack(
        target="valuecell_web",
        valuecell_prompt="scan portfolio risk",
        expected_sections=["summary", "risk_rating"],
        browser_steps=[BrowserStep(action="open_chat"), BrowserStep(action="submit")],
        timeout_seconds=900,
    )

    outcome = runner.execute(
        task_id="task_fail",
        execution_pack=execution_pack,
        adapter=FakeAdapter(fail_at="submit_prompt"),
    )

    assert outcome.status == "needs_manual_intervention"
    assert outcome.failed_step == "submit_prompt"
    assert "submit_prompt failed" in (outcome.error_message or "")
    assert outcome.duration_seconds is not None
    assert outcome.step_history
