from __future__ import annotations

import os
from typing import Any


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
        MVP阶段占位接口。

        后续接入 OpenAI SDK:
        base_url=https://api.deepseek.com
        """

        if not self.available():
            raise RuntimeError(
                "DeepSeek API key is missing"
            )

        raise NotImplementedError(
            "DeepSeek request implementation pending"
        )
