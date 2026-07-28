from __future__ import annotations

from typing import Protocol


SERVICE_NAME = "ai-video-production-verifier"
USERNAME = "deepseek_api_key"


class KeyringBackend(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...
    def set_password(self, service_name: str, username: str, password: str) -> None: ...
    def delete_password(self, service_name: str, username: str) -> None: ...


class CredentialError(Exception):
    pass


def _backend() -> KeyringBackend:
    import keyring

    return keyring


def load_api_key(backend: KeyringBackend | None = None) -> str | None:
    try:
        return (backend or _backend()).get_password(SERVICE_NAME, USERNAME)
    except Exception as exc:
        raise CredentialError("无法读取已保存的API Key。") from exc


def save_api_key(api_key: str, backend: KeyringBackend | None = None) -> None:
    cleaned = api_key.strip()
    if not cleaned:
        raise CredentialError("API Key不能为空。")
    try:
        (backend or _backend()).set_password(SERVICE_NAME, USERNAME, cleaned)
    except Exception as exc:
        raise CredentialError("无法保存API Key。") from exc


def clear_api_key(backend: KeyringBackend | None = None) -> None:
    try:
        (backend or _backend()).delete_password(SERVICE_NAME, USERNAME)
    except Exception as exc:
        # keyring raises when no credential exists; clearing is still idempotent.
        if exc.__class__.__name__ != "PasswordDeleteError":
            raise CredentialError("无法清除API Key。") from exc
