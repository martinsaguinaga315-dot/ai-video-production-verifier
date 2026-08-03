from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


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
        model: str = "deepseek-chat",
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

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
        except Exception as exc:
            raise RuntimeError("DeepSeek API request failed") from exc

        if not content:
            raise RuntimeError("DeepSeek returned an empty response")

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("DeepSeek returned invalid JSON") from exc

        if not isinstance(result, dict):
            raise RuntimeError("DeepSeek response JSON must be an object")

        return result
