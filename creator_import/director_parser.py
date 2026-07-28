from __future__ import annotations

from models import DirectorOutput, ProjectFacts

from creator_import.extraction_errors import ExtractionValidationError
from creator_import.json_repair import parse_with_bounded_repair, repair_with_client
from creator_import.prompt_templates import DIRECTOR_SYSTEM_PROMPT, director_user_prompt


def parse_director_output_from_text(text: str, facts: ProjectFacts, client) -> DirectorOutput:
    if not text.strip():
        raise ExtractionValidationError("导演方案或分镜方案不能为空。")
    raw = client.request_json(DIRECTOR_SYSTEM_PROMPT, director_user_prompt(text, facts))
    # Deliberately do not hide conflicts here. Existing hard rules own them.
    return parse_with_bounded_repair(
        raw,
        DirectorOutput,
        lambda invalid, problems: repair_with_client(client, invalid, problems),
    )
