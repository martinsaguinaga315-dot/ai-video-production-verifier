from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
SUPPORTED_DEEPSEEK_MODELS = ("deepseek-v4-flash", "deepseek-v4-pro")
DEFAULT_MAX_TOKENS = 4096


class DeepSeekApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, error_code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class DeepSeekClient:
    """
    AI Creator 专用 DeepSeek 客户端。

    只负责：
    - API 调用
    - 参数管理
    - 返回解析

    不负责：
    - 创意逻辑
    - Prompt设计
    - Story生成
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        timeout: int = 45,
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key)

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        thinking: bool | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        """
        Generate a JSON object through DeepSeek's OpenAI-compatible API.
        """

        if not self.available():
            raise RuntimeError(
                "DeepSeek API key is missing"
            )

        client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com",
            timeout=self.timeout,
        )

        content = None
        finish_reason = None
        for attempt in range(2):
            try:
                request: dict[str, Any] = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": max_tokens,
                }
                if thinking is not None:
                    request["extra_body"] = {"thinking": {"type": "enabled" if thinking else "disabled"}}
                response = client.chat.completions.create(**request)
                choice = response.choices[0]
                content = choice.message.content
                finish_reason = choice.finish_reason
            except Exception as exc:
                raise self._api_error(exc) from exc
            if content:
                break
        if not content:
            if finish_reason == "length":
                raise DeepSeekApiError(
                    "DeepSeek output reached the length limit without complete content",
                    error_code="length_empty",
                )
            raise DeepSeekApiError("DeepSeek returned an empty response", error_code="empty_content")

        result = self._parse_json_object(content)

        if not isinstance(result, dict):
            raise RuntimeError("DeepSeek response JSON must be an object")

        return result

    @staticmethod
    def _api_error(exc: Exception) -> DeepSeekApiError:
        status = getattr(exc, "status_code", None)
        body = getattr(exc, "body", None)
        code = body.get("code") if isinstance(body, dict) else None
        if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
            return DeepSeekApiError("DeepSeek request timed out", error_code="timeout")
        if "connection" in type(exc).__name__.lower() or "connect" in str(exc).lower():
            return DeepSeekApiError("Unable to connect to DeepSeek API", error_code="connection")
        return DeepSeekApiError("DeepSeek API request failed", status_code=status, error_code=code)

    @classmethod
    def _parse_json_object(cls, content: str) -> dict[str, Any]:
        """Parse a response, allowing only a fenced or singly embedded object."""
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = cls._recover_json_object(content)
        if not isinstance(result, dict):
            raise RuntimeError("DeepSeek response JSON must be an object")
        return result

    @classmethod
    def _recover_json_object(cls, content: str) -> Any:
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                fenced_body = "\n".join(lines[1:-1]).strip()
                try:
                    return json.loads(fenced_body)
                except json.JSONDecodeError:
                    content = fenced_body

        objects = cls._complete_json_objects(content)
        if len(objects) > 1:
            raise RuntimeError("DeepSeek returned multiple conflicting JSON objects")
        if len(objects) == 1:
            try:
                return json.loads(objects[0])
            except json.JSONDecodeError as exc:
                raise RuntimeError("DeepSeek returned unrecoverable JSON content") from exc
        if "{" in content:
            raise RuntimeError("DeepSeek returned truncated JSON response")
        raise RuntimeError("DeepSeek returned invalid JSON")

    @staticmethod
    def _complete_json_objects(content: str) -> list[str]:
        objects: list[str] = []
        start: int | None = None
        depth = 0
        in_string = False
        escaped = False
        for index, char in enumerate(content):
            if start is None:
                if char == "{":
                    start = index
                    depth = 1
                continue
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    objects.append(content[start:index + 1])
                    start = None
        return objects
