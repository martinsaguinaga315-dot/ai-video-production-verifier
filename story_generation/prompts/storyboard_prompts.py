from __future__ import annotations


import json
from typing import Any

from story_generation.models import GenerationIssue, StoryboardDraft


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

你必须只返回一个 JSON object。禁止 Markdown、禁止 ```json 代码块、禁止 JSON 前后的任何说明文字。

顶层结构必须是：
{
  "title": "string",
  "target_duration_s": 60,
  "shots": [ ... ]
}

shots 必须是非空数组。每个镜头至少包含 sequence、duration_s、camera、action、performance、first_frame_prompt、video_prompt。
第一镜头从 0 秒开始；duration_s 必须为正数；所有镜头 duration_s 的总和必须严格等于 60 秒；镜头之间不得有空档或重叠。
不要输出 provenance；系统会在后续处理时补齐。
在输出前自行复核镜头总时长是否为 60 秒。
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

请生成结构化 Storyboard，并严格遵守系统 JSON 契约。

精简格式示例（仅示例字段与格式；实际 shots 必须非空且 duration_s 总和为 60）：
{{
  "title": "地下接驳舱",
  "target_duration_s": 60,
  "shots": [
    {{
      "sequence": 1,
      "duration_s": 6,
      "camera": "低角度固定全景",
      "action": "接驳舱门缓缓开启。",
      "performance": "人物谨慎、克制。",
      "first_frame_prompt": "工业科幻接驳舱，舱门关闭，电影级光影。",
      "video_prompt": "低角度固定全景，接驳舱门缓缓开启，电影感运动。"
    }}
  ]
}}
"""


_REPAIR_INSTRUCTIONS = {
    "DURATION_MISMATCH": "重新分配正数 duration_s，使总和严格等于目标时长。",
    "SHOT_TIME_OVERLAP": "按 sequence 输出连续时间轴，不允许镜头重叠。",
    "NONCONTIGUOUS_SEQUENCE": "sequence 从 1 开始，无重复、无跳号。",
}
_INTERNAL_FIELDS = {"provenance", "field_provenance", "storyboard_id", "scene_plan_id", "shot_id", "scene_id", "location_id"}


def build_storyboard_repair_prompt(storyboard: StoryboardDraft, issues: list[GenerationIssue], target_duration_s: float, parent_request_id: str | None = None) -> str:
    sanitized = _remove_internal_fields(storyboard.model_dump(mode="json"))
    issue_details = "\n".join(
        f"- {item.code.value}: {item.message}\n  修正要求：{_REPAIR_INSTRUCTIONS[item.code.value]}"
        for item in issues if item.code.value in _REPAIR_INSTRUCTIONS
    )
    return f"""
这是一次 Storyboard 验证失败后的单次修正。请返回完整替换后的 storyboard，不是 patch。
首次 generation_request_id：{parent_request_id or "未提供"}
目标总时长：{target_duration_s} 秒。

已检测问题：
{issue_details}

原 Storyboard（已移除 provenance、field_provenance 和内部追踪字段）：
{json.dumps(sanitized, ensure_ascii=False, indent=2)}

只输出一个 JSON object。禁止 Markdown、禁止 ```json code fence、禁止 JSON 外的任何文字。
顶层必须包含 title、target_duration_s 和非空 shots。所有 duration_s 必须为正数，duration_s 总和必须严格等于 {target_duration_s} 秒。
输出完整替换结果，并在输出前自行复核上述问题均已修正。
"""


def _remove_internal_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _remove_internal_fields(item) for key, item in value.items() if key not in _INTERNAL_FIELDS}
    if isinstance(value, list):
        return [_remove_internal_fields(item) for item in value]
    return value
