from __future__ import annotations

import math

from models import ProjectFacts

from creator_import.extraction_errors import ExtractionValidationError
from creator_import.json_repair import parse_with_bounded_repair, repair_with_client
from creator_import.prompt_templates import FACTS_SYSTEM_PROMPT, facts_user_prompt


def _validate_fact_timeline(facts: ProjectFacts) -> ProjectFacts:
    problems: list[str] = []
    if facts.shot_count != len(facts.shots):
        problems.append("镜头数量与镜头列表数量不一致。")
    if facts.shots and not math.isclose(facts.total_duration, facts.shots[-1].end_time, abs_tol=0.01):
        problems.append("总时长与最后镜头结束时间不一致。")
    if problems:
        raise ExtractionValidationError("自动结构化失败。", problems)
    return facts


def extract_facts_from_text(text: str, client) -> ProjectFacts:
    if not text.strip():
        raise ExtractionValidationError("剧本或项目要求不能为空。")
    raw = client.request_json(FACTS_SYSTEM_PROMPT, facts_user_prompt(text))
    facts = parse_with_bounded_repair(
        raw,
        ProjectFacts,
        lambda invalid, problems: repair_with_client(client, invalid, problems),
    )
    return _validate_fact_timeline(facts)
