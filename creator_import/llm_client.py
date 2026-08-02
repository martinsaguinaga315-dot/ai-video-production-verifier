"""One safe DeepSeek-compatible client for creator-mode structured calls."""
from __future__ import annotations

import os
import time
from typing import Protocol

from openai import OpenAI

from creator_desktop.credentials import CredentialError, load_api_key
from creator_import.extraction_errors import LLMRequestError


class JsonLLM(Protocol):
    def request_json(self, system_prompt: str, user_prompt: str) -> str: ...


def _error_code(error: Exception) -> str:
    status = getattr(error, "status_code", None)
    if status == 401:
        return "api_key_invalid"
    if status == 429:
        return "rate_limited"
    if status in (402, 403):
        return "insufficient_permission"
    if isinstance(status, int) and status >= 500:
        return "service_unavailable"
    name = type(error).__name__.lower()
    if "timeout" in name or isinstance(error, TimeoutError):
        return "timeout"
    if "connection" in name or "connect" in name:
        return "connection_failed"
    return "llm_failed"


_MESSAGES = {
    "api_key_missing": "未配置DeepSeek API Key。",
    "api_key_invalid": "API Key无效。",
    "timeout": "请求超时，请稍后重试。",
    "connection_failed": "无法连接DeepSeek，请检查网络。",
    "rate_limited": "请求频率过高，请稍后重试。",
    "insufficient_permission": "账户余额不足或没有访问权限。",
    "service_unavailable": "DeepSeek服务暂时不可用。",
    "empty_response": "DeepSeek返回内容为空。",
}


class DeepSeekClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 45,
        max_attempts: int = 2,
        client=None,
    ) -> None:
        if api_key is None:
            try:
                api_key = load_api_key()
            except CredentialError as exc:
                raise LLMRequestError(_MESSAGES["api_key_missing"], "api_key_missing") from exc
        if not api_key or not api_key.strip():
            raise LLMRequestError(_MESSAGES["api_key_missing"], "api_key_missing")
        self._api_key = api_key.strip()
        self._model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
        self._max_attempts = max(1, min(max_attempts, 2))
        self._client = client or OpenAI(
            api_key=self._api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
            timeout=timeout_seconds,
        )

    def request_json(self, system_prompt: str, user_prompt: str) -> str:
        for attempt in range(self._max_attempts):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=8000,
                    stream=False,
                )
                content = response.choices[0].message.content or ""
                if not content.strip():
                    raise LLMRequestError(_MESSAGES["empty_response"], "empty_response")
                return content
            except LLMRequestError:
                raise
            except Exception as exc:
                code = _error_code(exc)
                if attempt + 1 < self._max_attempts and code in {"timeout", "connection_failed", "service_unavailable"}:
                    time.sleep(0.25)
                    continue
                raise LLMRequestError(_MESSAGES.get(code, "DeepSeek请求失败。"), code) from exc
        raise LLMRequestError("DeepSeek请求失败。")
