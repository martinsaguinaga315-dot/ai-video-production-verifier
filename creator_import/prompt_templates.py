from __future__ import annotations

import json

from models import DirectorOutput, ProjectFacts


FACTS_SYSTEM_PROMPT = """你是影视项目事实提取器，不是导演。只提取用户文本明确支持的事实，不得增加人物、道具、台词或剧情，不得把氛围词、'有人'、'远处学生'等模糊描述当作固定人物。精确台词保持原文。时间无法确定时保持保守并返回JSON。只输出JSON。"""

DIRECTOR_SYSTEM_PROMPT = """你是导演方案结构化器，不是编剧。忠实把用户提供的导演方案转为JSON；facts是不可随意改变的约束。不得新增人物、道具、台词、镜头或剧情。若用户原文和facts冲突，保留原文冲突供核验器报告，不要偷偷修正。缺少纯描述字段时只作最小、保守补全。只输出JSON。"""


def facts_user_prompt(text: str) -> str:
    return json.dumps(
        {"task": "提取ProjectFacts", "schema": ProjectFacts.model_json_schema(), "source_text": text},
        ensure_ascii=False,
    )


def director_user_prompt(text: str, facts: ProjectFacts) -> str:
    return json.dumps(
        {
            "task": "解析DirectorOutput",
            "facts": facts.model_dump(mode="json"),
            "schema": DirectorOutput.model_json_schema(),
            "source_text": text,
        },
        ensure_ascii=False,
    )


def repair_user_prompt(invalid_response: str, problems: list[str]) -> str:
    return json.dumps(
        {
            "task": "仅修复为合法JSON，不补充文本中不存在的事实",
            "validation_problems": problems[:8],
            "invalid_response": invalid_response,
        },
        ensure_ascii=False,
    )
