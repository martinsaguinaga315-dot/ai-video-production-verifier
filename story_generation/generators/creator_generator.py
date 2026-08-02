from __future__ import annotations

from story_generation.prompts.storyboard_prompts import (
    build_storyboard_prompt,
)


class CreatorGenerator:
    """
    AI Creator 第一阶段生成器。

    当前职责：
    - 接收创意输入
    - 构造生成 Prompt
    - 返回结构化生成请求

    后续：
    - 接入 DeepSeekClient
    - 输出 StoryboardDraft
    """

    def __init__(self):
        pass

    def build_request(
        self,
        idea: str,
        style: str | None = None,
        goal: str | None = None,
    ) -> dict:
        prompt = build_storyboard_prompt(
            idea=idea,
            style=style,
            goal=goal,
        )

        return {
            "type": "storyboard_generation",
            "idea": idea,
            "style": style,
            "goal": goal,
            "prompt": prompt,
        }
