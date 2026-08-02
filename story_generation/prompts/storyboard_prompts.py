from __future__ import annotations


STORYBOARD_GENERATION_SYSTEM_PROMPT = """
你是一名专业电影导演、分镜师和AI视频提示词设计师。

你的任务：
根据用户提供的创意，生成结构化视频制作方案。

要求：

1. 保持人物连续性
2. 保持场景连续性
3. 明确镜头语言
4. 输出可用于AI视频生成的提示词
5. 不允许虚构用户未确认的重要事实

输出必须符合JSON结构。
"""


def build_storyboard_prompt(
    idea: str,
    style: str | None = None,
    goal: str | None = None,
) -> str:
    return f"""
用户创意：

{idea}

视觉风格：

{style or "未指定"}

制作目标：

{goal or "生成电影级视频分镜"}

请生成结构化Storyboard。
"""
