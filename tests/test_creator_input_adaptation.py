from __future__ import annotations

from creator_import.compact_director_models import CompactDirectorDraft
from creator_import.director_parser import _append_supported_events, build_director_output_from_compact_draft
from models import DirectorOutput, ProjectFacts
from rules import verify


def character_facts() -> ProjectFacts:
    return ProjectFacts.model_validate({
        "title": "人物适配", "total_duration": 3, "shot_count": 1,
        "characters": [{
            "character_id": "林舟",
            "fixed_appearance_terms": ["25岁", "东亚男性"],
            "initial_state_terms": ["头发潮湿"],
        }],
        "props": [],
        "shots": [{"shot_id": "S01", "start_time": 0, "end_time": 3}],
    })


def compact_character(**overrides: object) -> CompactDirectorDraft:
    character = {"character_id": "林舟", **overrides}
    return CompactDirectorDraft.model_validate({
        "characters": [character],
        "shots": [{"shot_id": "S01", "opening_state": "林舟站在门口", "action_path": "林舟等待"}],
    })


def test_empty_appearance_evidence_inherits_reviewed_character_baseline() -> None:
    output = build_director_output_from_compact_draft(
        compact_character(), character_facts(), "林舟站在门口。",
    )
    character = output.characters[0]
    assert character.fixed_appearance == "25岁，东亚男性"
    assert character.initial_state == "头发潮湿"
    assert "APPEARANCE_MISSING" not in {issue.rule_id for issue in verify(character_facts(), output).issues}


def test_verified_appearance_evidence_normalizes_to_fact_terms() -> None:
    source = "25岁的东亚男性林舟站在门口。"
    output = build_director_output_from_compact_draft(
        compact_character(fixed_appearance="25岁的东亚男性", appearance_source_quote="25岁的东亚男性林舟"),
        character_facts(), source,
    )
    assert output.characters[0].fixed_appearance == "25岁，东亚男性"


def test_verified_conflicting_appearance_is_not_overwritten_by_facts() -> None:
    source = "40岁的欧美男性林舟站在门口。"
    output = build_director_output_from_compact_draft(
        compact_character(fixed_appearance="40岁的欧美男性", appearance_source_quote="40岁的欧美男性林舟"),
        character_facts(), source,
    )
    assert output.characters[0].fixed_appearance == "40岁的欧美男性"
    assert "APPEARANCE_MISSING" in {issue.rule_id for issue in verify(character_facts(), output).issues}


def test_forged_appearance_quote_does_not_enable_baseline_inheritance() -> None:
    output = build_director_output_from_compact_draft(
        compact_character(appearance_source_quote="不存在的外观描述"), character_facts(), "林舟站在门口。",
    )
    assert output.characters[0].fixed_appearance == ""
    assert "APPEARANCE_MISSING" in {issue.rule_id for issue in verify(character_facts(), output).issues}


def event_facts() -> ProjectFacts:
    return ProjectFacts.model_validate({
        "title": "事件适配", "total_duration": 3, "shot_count": 1,
        "characters": [], "props": [],
        "shots": [{
            "shot_id": "S01", "start_time": 0, "end_time": 3,
            "required_events": ["站在公交站", "穿深蓝夹克", "拿白色信封", "抬头"],
        }],
    })


def empty_event_output(action_path: str = "自由动作描述") -> DirectorOutput:
    return DirectorOutput.model_validate({
        "shots": [{
            "shot_id": "S01", "start_time": 0, "end_time": 3, "final_duration": 3,
            "action_path": action_path,
        }],
    })


def supported(event: str, quote: str) -> dict[str, object]:
    return {"shot_id": "S01", "required_event": event, "supported": True, "source_quote": quote}


def test_event_block_is_front_loaded_and_sorted_by_source_position() -> None:
    source = "站在公交站，穿深蓝夹克，拿白色信封，最后抬头。"
    result = _append_supported_events(empty_event_output(), event_facts(), [
        supported("抬头", "抬头"),
        supported("拿白色信封", "拿白色信封"),
        supported("穿深蓝夹克", "穿深蓝夹克"),
        supported("站在公交站", "站在公交站"),
    ], source)
    action_path = result.shots[0].action_path
    assert action_path.startswith("固定事实事件：")
    positions = [action_path.index(event) for event in event_facts().shots[0].required_events]
    assert positions == sorted(positions)
    assert action_path.index("自由动作描述") > positions[-1]


def test_wrong_source_order_is_preserved_instead_of_reordered_to_facts() -> None:
    source = "先抬头，再拿白色信封，穿深蓝夹克，站在公交站。"
    result = _append_supported_events(empty_event_output(), event_facts(), [
        supported("站在公交站", "站在公交站"),
        supported("穿深蓝夹克", "穿深蓝夹克"),
        supported("拿白色信封", "拿白色信封"),
        supported("抬头", "抬头"),
    ], source)
    action_path = result.shots[0].action_path
    positions = [action_path.index(event) for event in ["抬头", "拿白色信封", "穿深蓝夹克", "站在公交站"]]
    assert positions == sorted(positions)


def test_repeated_quotes_consume_earliest_unused_source_occurrences() -> None:
    facts = ProjectFacts.model_validate({
        "title": "重复引文", "total_duration": 3, "shot_count": 1, "characters": [], "props": [],
        "shots": [{"shot_id": "S01", "start_time": 0, "end_time": 3, "required_events": ["事件甲", "事件乙"]}],
    })
    result = _append_supported_events(empty_event_output(), facts, [
        supported("事件甲", "重复"), supported("事件乙", "重复"),
    ], "重复，然后重复。")
    assert result.shots[0].action_path.count("事件甲") == 1
    assert result.shots[0].action_path.count("事件乙") == 1


def test_existing_exact_event_is_not_repeated_in_event_block() -> None:
    source = "站在公交站，随后抬头。"
    result = _append_supported_events(empty_event_output("抬头后的自由描述"), event_facts(), [
        supported("站在公交站", "站在公交站"), supported("抬头", "抬头"),
    ], source)
    assert result.shots[0].action_path.count("抬头") == 1


def test_forged_and_wrong_shot_evidence_never_enters_event_block() -> None:
    source = "站在公交站。"
    result = _append_supported_events(empty_event_output(), event_facts(), [
        supported("穿深蓝夹克", "伪造引文"),
        {"shot_id": "other", "required_event": "站在公交站", "supported": True, "source_quote": "站在公交站"},
    ], source)
    assert "穿深蓝夹克" not in result.shots[0].action_path
    assert "站在公交站" not in result.shots[0].action_path
