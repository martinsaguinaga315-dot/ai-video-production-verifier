"""Safe UI state derived only from whether a credential exists."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiKeyDialogState:
    has_saved_key: bool
    input_value: str = ""

    @property
    def status_text(self) -> str:
        return (
            "API Key状态：已安全保存到Windows系统凭据"
            if self.has_saved_key
            else "API Key状态：尚未配置"
        )

    @property
    def status_color(self) -> str:
        return "#2e8b57" if self.has_saved_key else "#b8860b"

    @property
    def save_button_text(self) -> str:
        return "保存并覆盖" if self.has_saved_key else "保存"

    @property
    def help_text(self) -> str:
        if self.has_saved_key:
            return "输入新的API Key并保存，可覆盖当前密钥。"
        return "配置后可使用DeepSeek语义审计。未配置时仍可使用本地硬规则模式。"

    def empty_save_notice(self) -> str:
        if self.has_saved_key:
            return "当前API Key已经安全保存，无需重复保存。\n如需更换，请输入新的API Key。"
        return "请输入DeepSeek API Key。"


def dialog_state(has_saved_key: bool) -> ApiKeyDialogState:
    """Create display state without receiving the credential value."""
    return ApiKeyDialogState(has_saved_key=has_saved_key)


def main_api_status(has_saved_key: bool) -> str:
    return "API：已配置" if has_saved_key else "API：未配置"


def semantic_mode_requires_configuration(has_saved_key: bool) -> bool:
    return not has_saved_key


def should_save_new_key(entry_value: str) -> bool:
    """Only a non-empty newly typed value may replace a saved credential."""
    return bool(entry_value.strip())
