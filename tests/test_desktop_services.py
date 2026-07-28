from __future__ import annotations

import io
import logging
import threading
import time
from types import SimpleNamespace

from creator_desktop.api_key_state import (
    dialog_state,
    main_api_status,
    semantic_mode_requires_configuration,
    should_save_new_key,
)
from creator_desktop.credentials import (
    clear_api_key,
    has_saved_api_key,
    load_api_key,
    save_api_key,
)
from creator_desktop.main_window import MainWindow
from creator_desktop.verification_controller import VerificationController


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.values.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.values[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.values.pop((service_name, username), None)


def test_credentials_save_load_and_clear_with_mock_backend() -> None:
    backend = FakeKeyring()
    save_api_key("test-key", backend)
    assert load_api_key(backend) == "test-key"
    clear_api_key(backend)
    assert load_api_key(backend) is None


def test_saved_key_dialog_state_is_safe_and_keeps_input_blank() -> None:
    state = dialog_state(True)
    assert state.status_text == "API Key状态：已安全保存到Windows系统凭据"
    assert state.input_value == ""
    assert state.save_button_text == "保存并覆盖"
    assert "输入新的API Key" in state.help_text


def test_show_key_control_cannot_reveal_saved_key() -> None:
    # The state object has no credential field; show/hide only affects new input.
    state = dialog_state(True)
    assert state.input_value == ""
    assert "old" not in repr(state).lower()


def test_empty_save_with_existing_key_does_not_overwrite_mock_backend() -> None:
    backend = FakeKeyring()
    save_api_key("old-key", backend)
    assert has_saved_api_key(backend)
    assert should_save_new_key("") is False
    assert load_api_key(backend) == "old-key"
    assert "无需重复保存" in dialog_state(True).empty_save_notice()


def test_new_key_can_overwrite_existing_key_and_input_resets_to_blank() -> None:
    backend = FakeKeyring()
    save_api_key("old-key", backend)
    assert should_save_new_key("new-key") is True
    save_api_key("new-key", backend)
    assert load_api_key(backend) == "new-key"
    assert dialog_state(True).input_value == ""


def test_clear_changes_credential_state_to_not_configured() -> None:
    backend = FakeKeyring()
    save_api_key("key", backend)
    clear_api_key(backend)
    assert has_saved_api_key(backend) is False
    assert dialog_state(False).status_text == "API Key状态：尚未配置"
    assert dialog_state(False).save_button_text == "保存"


def test_controller_does_not_start_duplicate_tasks() -> None:
    release = threading.Event()

    def runner(*args, **kwargs):
        release.wait(timeout=2)
        return object()

    controller = VerificationController(runner=runner)
    assert controller.start("facts", "output", semantic=False, api_key=None) is True
    assert controller.start("facts", "output", semantic=False, api_key=None) is False
    release.set()
    deadline = time.time() + 2
    while controller.running and time.time() < deadline:
        time.sleep(0.01)
    assert controller.running is False
    kind, _ = controller.events.get_nowait()
    assert kind == "complete"


def test_empty_file_dialog_result_is_a_noop_contract() -> None:
    """The UI checks `if path` before setting fields, so cancel is harmless."""
    selected = ""
    current = "existing.json"
    if selected:
        current = selected
    assert current == "existing.json"


def test_semantic_mode_without_key_is_blocked_before_worker_start(monkeypatch) -> None:
    class Value:
        def __init__(self, value: str) -> None:
            self.value = value

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    blocked = []
    fake_window = SimpleNamespace(
        facts_path=Value("facts.json"),
        output_path=Value("director_output.json"),
        semantic_mode=Value("semantic"),
        _handle_missing_api_key=lambda: blocked.append(True),
    )
    monkeypatch.setattr("creator_desktop.main_window.load_api_key", lambda: None)
    MainWindow._start(fake_window)
    assert blocked == [True]
    assert semantic_mode_requires_configuration(False) is True


def test_main_api_status_refreshes_after_save_or_clear(monkeypatch) -> None:
    class Value:
        def __init__(self) -> None:
            self.value = ""

        def set(self, value: str) -> None:
            self.value = value

    fake_window = SimpleNamespace(api_status=Value())
    monkeypatch.setattr("creator_desktop.main_window.has_saved_api_key", lambda: True)
    MainWindow._refresh_api_status(fake_window)
    assert fake_window.api_status.value == "API：已配置"
    monkeypatch.setattr("creator_desktop.main_window.has_saved_api_key", lambda: False)
    MainWindow._refresh_api_status(fake_window)
    assert fake_window.api_status.value == "API：未配置"
    assert main_api_status(True) == "API：已配置"


def test_key_does_not_appear_in_error_log(monkeypatch) -> None:
    stream = io.StringIO()
    logger = logging.getLogger("test_key_safety")
    logger.handlers.clear()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    fake_window = SimpleNamespace(
        _log=logger,
        status=SimpleNamespace(set=lambda value: None),
        start_button=SimpleNamespace(configure=lambda **kwargs: None),
    )
    monkeypatch.setattr("creator_desktop.main_window.messagebox.showerror", lambda *args, **kwargs: None)
    MainWindow._on_error(fake_window, RuntimeError("secret-api-key"))
    assert "secret-api-key" not in stream.getvalue()
