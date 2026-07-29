from __future__ import annotations

import json

from creator_import.compact_director_models import CompactDirectorDraft
from models import ProjectFacts


FACTS_SYSTEM_PROMPT = """你是影视项目事实提取器，不是导演。只提取用户文本明确支持的事实，不得增加人物、道具、台词或剧情，不得把氛围词、'有人'、'远处学生'等模糊描述当作固定人物。精确台词保持原文。时间无法确定时保持保守并返回JSON。只输出JSON。"""

DIRECTOR_SYSTEM_PROMPT = """你是导演方案结构化器，不是编剧。只返回精简导演草稿JSON，忠实提取用户导演原文；不得新增人物、道具、台词、镜头或剧情，冲突必须保留给核验器。

每个人物的appearance_source_quote必须是导演原文中连续的外观描述；原文未描述外观时返回空字符串。不得用猜测、facts或改写文本充当引文。
每个道具的owner_source_quote必须是导演原文中连续的归属描述；原文未说明归属时返回空字符串。不得用猜测、facts或改写文本充当引文。
不得返回start_time、end_time、final_duration、first_frame_prompt、video_prompt、generation_segments或完整facts。每个shot只保留shot_id、人物、开场状态、动作、表演、台词、声音、结尾状态、负面约束和本镜头的required_event_support。引文必须是导演原文真实连续片段。不得输出Markdown或解释文字。"""


def facts_user_prompt(text: str) -> str:
    return json.dumps(
        {"task": "提取ProjectFacts", "schema": ProjectFacts.model_json_schema(), "source_text": text},
        ensure_ascii=False,
    )


def director_user_prompt(text: str, facts: ProjectFacts, fact_shots=None, *, batch_index: int = 1, batch_total: int = 1) -> str:
    shots = fact_shots if fact_shots is not None else facts.shots
    return json.dumps(
        {
            "task": "解析精简导演草稿",
            "batch": f"{batch_index}/{batch_total}",
            "facts_summary": {"title": facts.title, "total_duration": facts.total_duration, "shots": [shot.model_dump(mode="json") for shot in shots]},
            "schema": CompactDirectorDraft.model_json_schema(),
            "source_text": text,
        },
        ensure_ascii=False,
    )


def compact_retry_prompt(text: str, facts: ProjectFacts, fact_shots, problems: list[str], batch_index: int, batch_total: int) -> str:
    return json.dumps({"task": "重新返回合法精简导演草稿JSON", "batch": f"{batch_index}/{batch_total}", "facts_summary": {"title": facts.title, "shots": [shot.model_dump(mode="json") for shot in fact_shots]}, "schema": CompactDirectorDraft.model_json_schema(), "previous_error": problems[:6], "source_text": text}, ensure_ascii=False)


def repair_user_prompt(invalid_response: str, problems: list[str]) -> str:
    return json.dumps(
        {
            "task": "仅修复为合法JSON，不补充文本中不存在的事实",
            "validation_problems": problems[:8],
            "invalid_response": invalid_response,
        },
        ensure_ascii=False,
    )
