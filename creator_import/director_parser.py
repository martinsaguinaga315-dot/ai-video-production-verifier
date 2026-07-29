from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from models import DirectorOutput, ProjectFacts
from rules import verify as verify_hard_rules

from creator_import.extraction_errors import ExtractionValidationError, JsonStructureError
from creator_import.compact_director_models import CompactDirectorDraft
from creator_import.json_cleanup import load_clean_json
from creator_import.json_repair import repair_with_client, validation_summary
from creator_import.prompt_templates import (
    DIRECTOR_SYSTEM_PROMPT,
    compact_retry_prompt,
    director_user_prompt,
)


LOGGER = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class AnchoredRequiredEvent:
    shot_id: str
    required_event: str
    source_quote: str
    source_start: int
    source_end: int


def _quote_positions(quote: str, source_text: str) -> list[tuple[int, int]]:
    """Return every normalized occurrence, in source order."""
    normalized_quote = _normalized_evidence(quote)
    normalized_source_parts: list[str] = []
    source_offsets: list[int] = []
    for source_index, char in enumerate(source_text):
        normalized_char = _normalized_evidence(char)
        if normalized_char:
            normalized_source_parts.append(normalized_char)
            source_offsets.extend([source_index] * len(normalized_char))
    normalized_source = "".join(normalized_source_parts)
    if not normalized_quote:
        return []
    positions: list[tuple[int, int]] = []
    start = 0
    while True:
        found = normalized_source.find(normalized_quote, start)
        if found < 0:
            return positions
        positions.append((source_offsets[found], source_offsets[found + len(normalized_quote) - 1] + 1))
        start = found + len(normalized_quote)


def _anchored_supported_events(
    facts: ProjectFacts,
    supports: list[dict[str, Any]],
    source_text: str,
) -> list[AnchoredRequiredEvent]:
    """Accept only evidenced fact events and retain their original order."""
    expected = {shot.shot_id: shot for shot in facts.shots}
    used_positions: dict[str, int] = {}
    anchored: list[AnchoredRequiredEvent] = []
    for support in supports:
        shot_id = str(support.get("shot_id", ""))
        event = str(support.get("required_event", ""))
        quote = str(support.get("source_quote", ""))
        normalized_quote = _normalized_evidence(quote)
        if (
            support.get("supported") is not True
            or shot_id not in expected
            or event not in expected[shot_id].required_events
        ):
            continue
        positions = _quote_positions(quote, source_text)
        occurrence_index = used_positions.get(normalized_quote, 0)
        if not positions or occurrence_index >= len(positions):
            continue
        source_start, source_end = positions[occurrence_index]
        used_positions[normalized_quote] = occurrence_index + 1
        anchored.append(AnchoredRequiredEvent(shot_id, event, quote, source_start, source_end))
    return anchored


def _append_supported_events(
    output: DirectorOutput,
    facts: ProjectFacts,
    supports: list[dict[str, Any]],
    source_text: str,
) -> DirectorOutput:
    """Anchor exact facts only after local validation of model-supplied evidence."""
    data = output.model_dump(mode="json")
    actual = {shot["shot_id"]: shot for shot in data["shots"]}
    by_shot: dict[str, list[AnchoredRequiredEvent]] = {}
    for anchored in _anchored_supported_events(facts, supports, source_text):
        if anchored.shot_id in actual:
            by_shot.setdefault(anchored.shot_id, []).append(anchored)

    for shot_id, anchored_events in by_shot.items():
        actual_shot = actual.get(shot_id)
        if not actual_shot:
            continue
        action_path = str(actual_shot.get("action_path", "")).strip()
        additions = [
            anchored.required_event
            for anchored in sorted(anchored_events, key=lambda item: item.source_start)
            if anchored.required_event not in action_path
        ]
        if additions:
            event_block = "固定事实事件：\n" + "\n".join(f"- {event}" for event in additions)
            actual_shot["action_path"] = (event_block + "\n\n" + action_path).strip()
    return DirectorOutput.model_validate(data)


def _narrative_from_existing_fields(shot: dict[str, Any]) -> str:
    action = str(shot.get("action_path", "")).strip()
    if action:
        return action
    parts = [
        str(shot.get("opening_state", "")).strip(),
        str(shot.get("performance", "")).strip(),
        str(shot.get("ending_state", "")).strip(),
    ]
    parts.extend(
        f"{item.get('speaker', '')}：{item.get('text', '')}".strip("：")
        for item in shot.get("dialogue", [])
        if isinstance(item, dict) and (item.get("speaker") or item.get("text"))
    )
    return "\n".join(part for part in parts if part)


def normalize_shot_generation_fields(shot: dict[str, Any]) -> dict[str, Any]:
    """Derive production fields only from existing fields in one sparse shot."""
    normalized = dict(shot)
    shot_id = str(normalized.get("shot_id", "")).strip()
    if not shot_id:
        raise ExtractionValidationError("自动结构化失败。", ["镜头无法生成分段名称：shot_id为空。"])
    try:
        duration = float(normalized.get("final_duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration <= 0:
        try:
            start, end = float(normalized.get("start_time")), float(normalized.get("end_time"))
        except (TypeError, ValueError):
            start, end = 0, 0
        if end <= start:
            raise ExtractionValidationError(
                "自动结构化失败。",
                [f"{shot_id}无法确定有效时长：final_duration无效，且end_time不大于start_time。"],
            )
        duration = end - start
    normalized["final_duration"] = duration
    first_frame = str(normalized.get("first_frame_prompt", "")).strip()
    if not first_frame:
        first_frame = str(normalized.get("opening_state", "")).strip()
    if not first_frame:
        raise ExtractionValidationError(
            "自动结构化失败。",
            [f"{shot_id}无法生成首帧提示词：first_frame_prompt和opening_state均为空。"],
        )
    normalized["first_frame_prompt"] = first_frame
    video_prompt = str(normalized.get("video_prompt", "")).strip()
    if not video_prompt:
        video_prompt = _narrative_from_existing_fields(normalized)
    if not video_prompt:
        raise ExtractionValidationError(
            "自动结构化失败。",
            [f"{shot_id}无法生成视频提示词：video_prompt、action_path、opening_state和ending_state均为空。"],
        )
    normalized["video_prompt"] = video_prompt
    return normalized


def _normalize_director_payload(candidate: Any) -> Any:
    if not isinstance(candidate, dict):
        return candidate
    normalized = dict(candidate)
    shots = normalized.get("shots")
    if isinstance(shots, list):
        normalized["shots"] = [
            normalize_shot_generation_fields(shot) if isinstance(shot, dict) else shot
            for shot in shots
        ]
    return normalized


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
            raise ExtractionValidationError("自动结构化失败。", [f"{shot.get('shot_id', '镜头')}无法生成合法分段。"])
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
            output = DirectorOutput.model_validate(_normalize_director_payload(candidate))
            output = _append_supported_events(output, facts, _support_items(data), source_text)
            return _complete_structure(output, facts)
        except (JsonStructureError, ValidationError, ExtractionValidationError) as exc:
            problems = exc.details if isinstance(exc, ExtractionValidationError) else validation_summary(exc)
            if repair_count >= 2:
                raise ExtractionValidationError("自动结构化失败。", problems) from exc
            current = repair_with_client(client, current, problems)
    raise ExtractionValidationError("自动结构化失败。", problems)


def _looks_like_complete_json(raw: str) -> bool:
    """Detect obvious truncation without retaining or logging response content."""
    text = raw.strip()
    return bool(text) and text.count("{") == text.count("}") and text.count("[") == text.count("]")


def _safe_parse_problems(raw: str, exc: Exception) -> list[str]:
    if not raw.strip():
        return ["DeepSeek未返回内容，请重新尝试。"]
    if not _looks_like_complete_json(raw):
        return ["DeepSeek返回内容不完整，软件将使用精简格式重新尝试。"]
    if isinstance(exc, ExtractionValidationError):
        return exc.details
    return validation_summary(exc)


def _batch_shot_ids(draft: CompactDirectorDraft, expected_ids: list[str]) -> None:
    actual_ids = [shot.shot_id for shot in draft.shots]
    duplicates = sorted({item for item in actual_ids if actual_ids.count(item) > 1})
    missing = [item for item in expected_ids if item not in actual_ids]
    unexpected = [item for item in actual_ids if item not in expected_ids]
    if duplicates or missing or unexpected:
        problems: list[str] = []
        if duplicates:
            problems.append("镜头ID重复：" + "、".join(duplicates))
        if missing:
            problems.append("缺少镜头ID：" + "、".join(missing))
        if unexpected:
            problems.append("存在不属于本批事实的镜头ID：" + "、".join(unexpected))
        raise ExtractionValidationError("自动结构化失败。", problems)


def _parse_compact_batch(
    raw: str,
    source_text: str,
    facts: ProjectFacts,
    fact_shots,
    client,
    batch_index: int,
    batch_total: int,
    status_callback: Callable[[str], None] | None = None,
) -> CompactDirectorDraft:
    """Parse one short response. A parser retry never sends the bad reply back."""
    current = raw
    expected_ids = [shot.shot_id for shot in fact_shots]
    problems: list[str] = []
    for attempt in range(2):
        try:
            if not _looks_like_complete_json(current):
                raise JsonStructureError("incomplete JSON")
            data = load_clean_json(current)
            candidate = data.get("director_draft", data) if isinstance(data, dict) else data
            draft = CompactDirectorDraft.model_validate(candidate)
            _batch_shot_ids(draft, expected_ids)
            LOGGER.info(
                "compact director draft parsed: batch=%s/%s attempt=%s chars=%s",
                batch_index, batch_total, attempt + 1, len(current),
            )
            return draft
        except (JsonStructureError, ValidationError, ExtractionValidationError) as exc:
            problems = _safe_parse_problems(current, exc)
            LOGGER.warning(
                "compact director draft parse failed: batch=%s/%s attempt=%s response_chars=%s error=%s",
                batch_index, batch_total, attempt + 1, len(current), type(exc).__name__,
            )
            if attempt == 1:
                raise ExtractionValidationError("自动结构化失败。", problems) from exc
            if status_callback:
                status_callback(f"导演方案格式不完整，正在重试第{batch_index}批（共{batch_total}批）")
            current = client.request_json(
                DIRECTOR_SYSTEM_PROMPT,
                compact_retry_prompt(source_text, facts, fact_shots, problems, batch_index, batch_total),
            )
    raise ExtractionValidationError("自动结构化失败。", problems)


def _merge_compact_drafts(drafts: list[CompactDirectorDraft], facts: ProjectFacts) -> CompactDirectorDraft:
    if not drafts:
        raise ExtractionValidationError("自动结构化失败。", ["没有可用的导演草稿。"])
    shots_by_id = {}
    for draft in drafts:
        for shot in draft.shots:
            if shot.shot_id in shots_by_id:
                raise ExtractionValidationError("自动结构化失败。", [f"镜头ID重复：{shot.shot_id}"])
            shots_by_id[shot.shot_id] = shot
    expected_ids = [shot.shot_id for shot in facts.shots]
    missing = [shot_id for shot_id in expected_ids if shot_id not in shots_by_id]
    unexpected = [shot_id for shot_id in shots_by_id if shot_id not in expected_ids]
    if missing or unexpected:
        details = (["缺少镜头ID：" + "、".join(missing)] if missing else []) + (
            ["存在未知镜头ID：" + "、".join(unexpected)] if unexpected else []
        )
        raise ExtractionValidationError("自动结构化失败。", details)
    first = drafts[0]
    return CompactDirectorDraft.model_validate({
        "project": first.project.model_dump(mode="json"),
        "characters": [item.model_dump(mode="json") for draft in drafts for item in draft.characters],
        "locations": [item for draft in drafts for item in draft.locations],
        "props": [item for draft in drafts for item in draft.props],
        "shots": [shots_by_id[shot_id].model_dump(mode="json") for shot_id in expected_ids],
    })


def _join_fact_terms(terms: list[str]) -> str:
    return "，".join(term.strip() for term in terms if term.strip())


def _source_quote_supports_terms(source_quote: str, terms: list[str]) -> bool:
    normalized_quote = _normalized_evidence(source_quote)
    return bool(normalized_quote) and all(
        _normalized_evidence(term) in normalized_quote
        for term in terms
        if _normalized_evidence(term)
    )


def _normalize_compact_characters(
    draft: CompactDirectorDraft, facts: ProjectFacts, source_text: str,
) -> list[dict[str, Any]]:
    """Safely inherit locked character baselines without hiding source conflicts."""
    locks = {lock.character_id: lock for lock in facts.characters}
    characters: list[dict[str, Any]] = []
    for compact_character in draft.characters:
        character = compact_character.model_dump(mode="json", exclude={"appearance_source_quote"})
        lock = locks.get(compact_character.character_id)
        if not lock:
            # Unknown characters remain in the output for the hard rules.
            characters.append(character)
            continue

        appearance_quote = compact_character.appearance_source_quote.strip()
        quote_is_valid = _quote_is_in_source(appearance_quote, source_text)
        fixed_appearance = str(character.get("fixed_appearance", "")).strip()
        if not appearance_quote:
            # No original appearance claim: retain the reviewed facts baseline.
            if not fixed_appearance:
                character["fixed_appearance"] = _join_fact_terms(lock.fixed_appearance_terms)
        elif quote_is_valid and _source_quote_supports_terms(appearance_quote, lock.fixed_appearance_terms):
            # The source confirms the facts, so use one canonical representation.
            character["fixed_appearance"] = _join_fact_terms(lock.fixed_appearance_terms)
        elif quote_is_valid and not fixed_appearance:
            # A real but non-supporting quote is a source conflict/variation. Keep
            # it visible so the existing hard rules can report it rather than
            # silently filling it with the facts baseline.
            character["fixed_appearance"] = appearance_quote

        if not str(character.get("initial_state", "")).strip():
            character["initial_state"] = _join_fact_terms(lock.initial_state_terms)
        characters.append(character)
    return characters


def build_director_output_from_compact_draft(
    draft: CompactDirectorDraft, facts: ProjectFacts, source_text: str,
) -> DirectorOutput:
    """Build all production-only fields locally from facts and the compact draft."""
    compact_shots = {shot.shot_id: shot for shot in draft.shots}
    output_shots: list[dict[str, Any]] = []
    supports: list[dict[str, Any]] = []
    for fact_shot in facts.shots:
        compact = compact_shots[fact_shot.shot_id]
        shot = compact.model_dump(mode="json", exclude={"required_event_support"})
        shot.update({
            "shot_id": fact_shot.shot_id,
            "start_time": fact_shot.start_time,
            "end_time": fact_shot.end_time,
            "final_duration": fact_shot.end_time - fact_shot.start_time,
            "first_frame_prompt": compact.opening_state,
            "video_prompt": compact.action_path,
            "generation_segments": [],
        })
        output_shots.append(normalize_shot_generation_fields(shot))
        supports.extend({"shot_id": fact_shot.shot_id, **item.model_dump(mode="json")} for item in compact.required_event_support)
    output = DirectorOutput.model_validate({
        "project": {"title": facts.title, "total_duration": facts.total_duration},
        "characters": _normalize_compact_characters(draft, facts, source_text),
        "locations": draft.locations,
        "props": draft.props,
        "shots": output_shots,
    })
    return _complete_structure(_append_supported_events(output, facts, supports, source_text), facts)


def _is_legacy_director_payload(raw: str) -> bool:
    """Keep previous integrations working while all new calls use compact drafts."""
    try:
        data = load_clean_json(raw)
    except JsonStructureError:
        return False
    candidate = data.get("director_output", data) if isinstance(data, dict) else {}
    shots = candidate.get("shots", []) if isinstance(candidate, dict) else []
    return isinstance(shots, list) and bool(shots) and isinstance(shots[0], dict) and "start_time" in shots[0]


def parse_director_output_from_text(
    text: str,
    facts: ProjectFacts,
    client,
    *,
    status_callback: Callable[[str], None] | None = None,
) -> DirectorOutput:
    if not text.strip():
        raise ExtractionValidationError("导演方案或分镜方案不能为空。")
    batches = [facts.shots[index:index + 4] for index in range(0, len(facts.shots), 4)]
    if not batches:
        raise ExtractionValidationError("自动结构化失败。", ["事实中没有镜头。"])
    if status_callback:
        status_callback(f"正在解析导演方案：第1批，共{len(batches)}批")
    raw = client.request_json(DIRECTOR_SYSTEM_PROMPT, director_user_prompt(text, facts, batches[0], batch_index=1, batch_total=len(batches)))
    if _is_legacy_director_payload(raw):
        output = _parse_response(raw, facts, text, client)
    else:
        drafts = [_parse_compact_batch(raw, text, facts, batches[0], client, 1, len(batches), status_callback)]
        for batch_index, fact_shots in enumerate(batches[1:], start=2):
            if status_callback:
                status_callback(f"正在解析导演方案：第{batch_index}批，共{len(batches)}批")
            batch_raw = client.request_json(
                DIRECTOR_SYSTEM_PROMPT,
                director_user_prompt(text, facts, fact_shots, batch_index=batch_index, batch_total=len(batches)),
            )
            drafts.append(_parse_compact_batch(batch_raw, text, facts, fact_shots, client, batch_index, len(batches), status_callback))
        output = build_director_output_from_compact_draft(_merge_compact_drafts(drafts, facts), facts, text)
    # Preflight deliberately observes the existing hard rules but never changes
    # user-originated conflicts, dialogue, or unsupported events.
    verify_hard_rules(facts, output)
    return output
