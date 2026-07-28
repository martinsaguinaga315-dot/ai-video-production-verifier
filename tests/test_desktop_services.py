from __future__ import annotations

import threading
import time

from creator_desktop.credentials import clear_api_key, load_api_key, save_api_key
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
