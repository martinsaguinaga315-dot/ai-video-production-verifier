from __future__ import annotations

from creator_import.compact_director_models import CompactDirectorDraft
from creator_import.director_parser import _append_supported_events, build_director_output_from_compact_draft
from llm_audit import _event_order_precheck, _identity_continuity_precheck
from models import DirectorOutput, ProjectFacts
from rules import verify
from tests.test_director_event_anchoring import base_output, rain_facts


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


def prop_facts() -> ProjectFacts:
    return ProjectFacts.model_validate({
        "title": "道具适配", "total_duration": 3, "shot_count": 1,
        "characters": [{"character_id": "林舟"}],
        "props": [{"prop_id": "白色信封", "owner": "林舟"}],
        "shots": [{"shot_id": "S01", "start_time": 0, "end_time": 3}],
    })


def compact_prop(**overrides: object) -> CompactDirectorDraft:
    prop = {"prop_id": "白色信封", **overrides}
    return CompactDirectorDraft.model_validate({
        "props": [prop],
        "shots": [{"shot_id": "S01", "opening_state": "林舟站在门口", "action_path": "林舟等待"}],
    })


def test_empty_prop_owner_inherits_confirmed_fact_owner() -> None:
    output = build_director_output_from_compact_draft(compact_prop(), prop_facts(), "林舟站在门口。")
    assert output.props[0]["owner"] == "林舟"
    assert "PROP_OWNER_MISMATCH" not in {issue.rule_id for issue in verify(prop_facts(), output).issues}


def test_verified_prop_owner_support_normalizes_to_fact_owner() -> None:
    source = "白色信封属于林舟。"
    output = build_director_output_from_compact_draft(
        compact_prop(owner="林舟", owner_source_quote="白色信封属于林舟"), prop_facts(), source,
    )
    assert output.props[0]["owner"] == "林舟"


def test_verified_conflicting_prop_owner_is_preserved_for_hard_rule() -> None:
    source = "白色信封属于苏然。"
    output = build_director_output_from_compact_draft(
        compact_prop(owner="苏然", owner_source_quote="白色信封属于苏然"), prop_facts(), source,
    )
    assert output.props[0]["owner"] == "苏然"
    assert "PROP_OWNER_MISMATCH" in {issue.rule_id for issue in verify(prop_facts(), output).issues}


def test_forged_prop_owner_quote_uses_confirmed_baseline_instead() -> None:
    output = build_director_output_from_compact_draft(
        compact_prop(owner="苏然", owner_source_quote="伪造的白色信封归属"), prop_facts(), "林舟站在门口。",
    )
    assert output.props[0]["owner"] == "林舟"
    assert "PROP_OWNER_MISMATCH" not in {issue.rule_id for issue in verify(prop_facts(), output).issues}


def test_unknown_prop_is_preserved_without_inheriting_another_owner() -> None:
    draft = CompactDirectorDraft.model_validate({
        "props": [{"prop_id": "红色雨伞", "owner": "苏然", "owner_source_quote": "红色雨伞属于苏然"}],
        "shots": [{"shot_id": "S01", "opening_state": "林舟站在门口", "action_path": "林舟等待"}],
    })
    output = build_director_output_from_compact_draft(draft, prop_facts(), "红色雨伞属于苏然。")
    assert output.props == [{"prop_id": "红色雨伞", "owner": "苏然"}]
    assert "UNKNOWN_PROP" in {issue.rule_id for issue in verify(prop_facts(), output).issues}


def test_appearance_conflict_fixture_inherits_prop_owner_without_extra_mismatch() -> None:
    facts = ProjectFacts.model_validate({
        "title": "外观冲突", "total_duration": 3, "shot_count": 1,
        "characters": [{"character_id": "林舟", "fixed_appearance_terms": ["25岁", "东亚男性"]}],
        "props": [{"prop_id": "白色信封", "owner": "林舟"}],
        "shots": [{"shot_id": "S01", "start_time": 0, "end_time": 3}],
    })
    source = "40岁的欧美男性林舟变成另一个人，拿着白色信封。"
    draft = CompactDirectorDraft.model_validate({
        "characters": [{"character_id": "林舟", "fixed_appearance": "40岁的欧美男性", "appearance_source_quote": "40岁的欧美男性林舟"}],
        "props": [{"prop_id": "白色信封"}],
        "shots": [{"shot_id": "S01", "characters": ["林舟"], "opening_state": "林舟站在门口", "action_path": "林舟变成另一个人"}],
    })
    output = build_director_output_from_compact_draft(draft, facts, source)
    hard_rule_ids = {issue.rule_id for issue in verify(facts, output).issues}
    identity_rule_ids = {issue.rule_id for issue in _identity_continuity_precheck(facts, output)}
    assert hard_rule_ids == {"APPEARANCE_MISSING"}
    assert identity_rule_ids == {"SEMANTIC_IDENTITY_CONTINUITY"}
    assert output.props[0]["owner"] == "林舟"


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
    assert action_path.startswith("固定事实事件（按导演原文顺序）：")
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


def test_existing_exact_event_is_still_anchored_and_free_action_is_preserved() -> None:
    source = "站在公交站，随后抬头。"
    result = _append_supported_events(empty_event_output("抬头后的自由描述"), event_facts(), [
        supported("站在公交站", "站在公交站"), supported("抬头", "抬头"),
    ], source)
    action_path = result.shots[0].action_path
    assert "- 抬头" in action_path
    assert action_path.count("抬头") == 2
    assert action_path.endswith("导演动作描述：\n抬头后的自由描述")


def test_event_block_deduplicates_only_its_own_events() -> None:
    source = "站在公交站，然后再次站在公交站。"
    result = _append_supported_events(empty_event_output("站在公交站的自由描述"), event_facts(), [
        supported("站在公交站", "站在公交站"),
        supported("站在公交站", "站在公交站"),
    ], source)
    event_block, free_action = result.shots[0].action_path.split("\n\n导演动作描述：\n", maxsplit=1)
    assert event_block.count("站在公交站") == 1
    assert free_action == "站在公交站的自由描述"


def _rain_shot2_supports() -> list[dict[str, object]]:
    return [
        {"shot_id": "shot2", "required_event": "林舟继续站在同一公交站", "supported": True, "source_quote": "继续站在同一公交站"},
        {"shot_id": "shot2", "required_event": "继续穿深蓝色夹克", "supported": True, "source_quote": "继续穿深蓝色夹克"},
        {"shot_id": "shot2", "required_event": "右手仍拿着同一封白色信封", "supported": True, "source_quote": "右手仍拿着同一封白色信封"},
        {"shot_id": "shot2", "required_event": "抬头看向道路尽头", "supported": True, "source_quote": "抬头看向道路尽头"},
    ]


def test_wrong_order_fixture_remains_visible_to_semantic_event_order_check() -> None:
    source = "林舟先缓慢抬头看向道路尽头，随后继续站在同一公交站，继续穿深蓝色夹克，右手仍拿着同一封白色信封。"
    output = DirectorOutput.model_validate(base_output())
    output.shots[1].action_path = "林舟先缓慢抬头看向道路尽头。"
    output.shots[1].video_prompt = output.shots[1].action_path
    result = _append_supported_events(output, rain_facts(), _rain_shot2_supports(), source)
    action_path = result.shots[1].action_path
    expected_order = ["抬头看向道路尽头", "林舟继续站在同一公交站", "继续穿深蓝色夹克", "右手仍拿着同一封白色信封"]
    assert [action_path.index(event) for event in expected_order] == sorted(action_path.index(event) for event in expected_order)
    assert action_path.endswith("导演动作描述：\n林舟先缓慢抬头看向道路尽头。")
    assert "SEMANTIC_EVENT_ORDER" in {issue.rule_id for issue in _event_order_precheck(rain_facts(), result)}


def test_correct_order_fixture_keeps_semantic_event_order_clean() -> None:
    source = "林舟继续站在同一公交站，继续穿深蓝色夹克，右手仍拿着同一封白色信封，随后抬头看向道路尽头。"
    output = DirectorOutput.model_validate(base_output())
    output.shots[1].action_path = "林舟随后抬头看向道路尽头。"
    output.shots[1].video_prompt = output.shots[1].action_path
    result = _append_supported_events(output, rain_facts(), _rain_shot2_supports(), source)
    assert "SEMANTIC_EVENT_ORDER" not in {issue.rule_id for issue in _event_order_precheck(rain_facts(), result)}


def test_forged_and_wrong_shot_evidence_never_enters_event_block() -> None:
    source = "站在公交站。"
    result = _append_supported_events(empty_event_output(), event_facts(), [
        supported("穿深蓝夹克", "伪造引文"),
        {"shot_id": "other", "required_event": "站在公交站", "supported": True, "source_quote": "站在公交站"},
    ], source)
    assert "穿深蓝夹克" not in result.shots[0].action_path
    assert "站在公交站" not in result.shots[0].action_path
