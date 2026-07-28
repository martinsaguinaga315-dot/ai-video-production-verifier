from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from models import DirectorOutput, ProjectFacts
from rules import verify as verify_hard_rules

from creator_import.extraction_errors import ExtractionValidationError, JsonStructureError
from creator_import.json_cleanup import load_clean_json
from creator_import.json_repair import repair_with_client, validation_summary
from creator_import.prompt_templates import DIRECTOR_SYSTEM_PROMPT, director_user_prompt


def _normalized_evidence(text: str) -> str:
    return re.sub(r"[\s，。、“”‘’：:；;！!？?（）()【】\[\]、]", "", text or "")


def _quote_is_in_source(quote: str, source_text: str) -> bool:
    normalized_quote = _normalized_evidence(quote)
    return bool(normalized_quote and normalized_quote in _normalized_evidence(source_text))


def _support_items(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    items = data.get("required_event_support", [])
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _append_supported_events(
    output: DirectorOutput,
    facts: ProjectFacts,
    supports: list[dict[str, Any]],
    source_text: str,
) -> DirectorOutput:
    """Anchor exact facts only after local validation of model-supplied evidence."""
    data = output.model_dump(mode="json")
    expected = {shot.shot_id: shot for shot in facts.shots}
    actual = {shot["shot_id"]: shot for shot in data["shots"]}
    supported_by_shot: dict[str, set[str]] = {}
    for support in supports:
        shot_id = str(support.get("shot_id", ""))
        event = str(support.get("required_event", ""))
        quote = str(support.get("source_quote", ""))
        if (
            support.get("supported") is True
            and shot_id in expected
            and shot_id in actual
            and event in expected[shot_id].required_events
            and _quote_is_in_source(quote, source_text)
        ):
            supported_by_shot.setdefault(shot_id, set()).add(event)

    for shot_id, expected_shot in expected.items():
        actual_shot = actual.get(shot_id)
        if not actual_shot:
            continue
        narrative = "\n".join(
            str(actual_shot.get(field, ""))
            for field in ("opening_state", "action_path", "ending_state", "video_prompt")
        )
        additions = [
            event
            for event in expected_shot.required_events
            if event in supported_by_shot.get(shot_id, set()) and event not in narrative
        ]
        if additions:
            suffix = "固定事实事件：\n" + "\n".join(f"- {event}" for event in additions)
            actual_shot["action_path"] = (str(actual_shot.get("action_path", "")).strip() + "\n\n" + suffix).strip()
    return DirectorOutput.model_validate(data)


def _complete_structure(output: DirectorOutput, facts: ProjectFacts) -> DirectorOutput:
    data = output.model_dump(mode="json")
    project = data.setdefault("project", {})
    if not project.get("title"):
        project["title"] = facts.title
    if project.get("total_duration") in (None, ""):
        project["total_duration"] = facts.total_duration
    for shot in data["shots"]:
        if shot.get("generation_segments"):
            continue
        required = (shot.get("shot_id"), shot.get("final_duration"), shot.get("first_frame_prompt"), shot.get("video_prompt"))
        if not all(required) or float(shot["final_duration"]) <= 0:
            raise ExtractionValidationError(
                "自动结构化失败。",
                [f"{shot.get('shot_id', '镜头')}缺少生成分段所需的名称、时长、首帧或视频提示词。"],
            )
        shot["generation_segments"] = [{
            "name": shot["shot_id"],
            "recommended_generation_duration": shot["final_duration"],
            "first_frame_prompt": shot["first_frame_prompt"],
            "video_prompt": shot["video_prompt"],
            "negative_constraints": list(shot.get("negative_constraints", [])),
        }]
    return DirectorOutput.model_validate(data)


def _parse_response(raw: str, facts: ProjectFacts, source_text: str, client) -> DirectorOutput:
    current = raw
    problems: list[str] = []
    for repair_count in range(3):
        try:
            data = load_clean_json(current)
            candidate = data.get("director_output", data) if isinstance(data, dict) else data
            output = DirectorOutput.model_validate(candidate)
            output = _append_supported_events(output, facts, _support_items(data), source_text)
            return _complete_structure(output, facts)
        except (JsonStructureError, ValidationError, ExtractionValidationError) as exc:
            problems = exc.details if isinstance(exc, ExtractionValidationError) else validation_summary(exc)
            if repair_count >= 2:
                raise ExtractionValidationError("自动结构化失败。", problems) from exc
            current = repair_with_client(client, current, problems)
    raise ExtractionValidationError("自动结构化失败。", problems)


def parse_director_output_from_text(text: str, facts: ProjectFacts, client) -> DirectorOutput:
    if not text.strip():
        raise ExtractionValidationError("导演方案或分镜方案不能为空。")
    raw = client.request_json(DIRECTOR_SYSTEM_PROMPT, director_user_prompt(text, facts))
    output = _parse_response(raw, facts, text, client)
    # Preflight deliberately observes the existing hard rules but never changes
    # user-originated conflicts, dialogue, or unsupported events.
    verify_hard_rules(facts, output)
    return output
