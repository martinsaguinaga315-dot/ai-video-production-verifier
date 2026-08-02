from __future__ import annotations

import json

from models import DirectorOutput, ProjectFacts
from rules import verify

from creator_import.director_parser import _append_supported_events, parse_director_output_from_text


class MockClient:
    def __init__(self, response: dict) -> None:
        self.response = json.dumps(response, ensure_ascii=False)
        self.calls = 0

    def request_json(self, system, user):
        self.calls += 1
        return self.response


def rain_facts() -> ProjectFacts:
    return ProjectFacts.model_validate({
        "title": "雨夜回信", "total_duration": 6, "shot_count": 2,
        "characters": [{"character_id": "林舟", "fixed_costume_terms": ["深蓝色夹克"], "fixed_props": ["白色信封"]}],
        "props": [{"prop_id": "白色信封", "owner": "林舟"}],
        "shots": [
            {"shot_id": "shot1", "start_time": 0, "end_time": 3, "required_events": ["林舟站在雨夜公交站下", "右手拿着白色信封", "低头看信封", "镜头结束时仍然拿着信封"], "exact_dialogue": []},
            {"shot_id": "shot2", "start_time": 3, "end_time": 6, "required_events": ["林舟继续站在同一公交站", "继续穿深蓝色夹克", "右手仍拿着同一封白色信封", "抬头看向道路尽头"], "exact_dialogue": [{"speaker": "林舟", "text": "我回来了。"}]},
        ],
    })


def base_output() -> dict:
    return {
        "project": {},
        "characters": [{"character_id": "林舟", "fixed_costume": "深蓝色夹克", "fixed_props": ["白色信封"]}],
        "props": [{"prop_id": "白色信封", "owner": "林舟"}],
        "shots": [
            {"shot_id": "shot1", "start_time": 0, "end_time": 3, "final_duration": 3, "characters": ["林舟"], "opening_state": "雨夜公交站", "action_path": "雨水从站棚边缘落下。", "ending_state": "林舟仍然拿着信封", "first_frame_prompt": "林舟站在站牌下", "video_prompt": "林舟站在站牌下，右手拿白色信封，低头注视信封", "negative_constraints": [], "generation_segments": []},
            {"shot_id": "shot2", "start_time": 3, "end_time": 6, "final_duration": 3, "characters": ["林舟"], "opening_state": "承接上一镜头，同一公交站", "action_path": "林舟抬眼望向远处。", "ending_state": "林舟站在站牌下", "first_frame_prompt": "同一公交站，深蓝色夹克", "video_prompt": "承接上一镜头，同一公交站，同一深蓝色夹克，右手仍拿同一封白色信封，抬眼望向远处", "dialogue": [{"speaker": "林舟", "text": "我回来了。"}], "negative_constraints": ["爆炸"], "generation_segments": []},
        ],
    }


SOURCE = "林舟穿深蓝色夹克，独自站在站牌下，右手拿白色信封，低头注视信封。镜头结束时林舟仍然拿着信封。承接上一镜头，同一公交站，同一深蓝色夹克，右手仍拿同一封白色信封，抬头看向道路尽头。林舟说：我回来了。"


def supports() -> list[dict]:
    return [
        {"shot_id": "shot1", "required_event": "林舟站在雨夜公交站下", "supported": True, "source_quote": "林舟穿深蓝色夹克，独自站在站牌下"},
        {"shot_id": "shot1", "required_event": "右手拿着白色信封", "supported": True, "source_quote": "右手拿白色信封"},
        {"shot_id": "shot1", "required_event": "低头看信封", "supported": True, "source_quote": "低头注视信封"},
        {"shot_id": "shot1", "required_event": "镜头结束时仍然拿着信封", "supported": True, "source_quote": "镜头结束时林舟仍然拿着信封"},
        {"shot_id": "shot2", "required_event": "林舟继续站在同一公交站", "supported": True, "source_quote": "承接上一镜头，同一公交站"},
        {"shot_id": "shot2", "required_event": "继续穿深蓝色夹克", "supported": True, "source_quote": "同一深蓝色夹克"},
        {"shot_id": "shot2", "required_event": "右手仍拿着同一封白色信封", "supported": True, "source_quote": "右手仍拿同一封白色信封"},
        {"shot_id": "shot2", "required_event": "抬头看向道路尽头", "supported": True, "source_quote": "抬头看向道路尽头"},
    ]


def test_supported_synonyms_anchor_exact_events_and_complete_segments() -> None:
    response = {"director_output": base_output(), "required_event_support": supports()}
    output = parse_director_output_from_text(SOURCE, rain_facts(), MockClient(response))
    assert all(event in output.shots[0].action_path for event in rain_facts().shots[0].required_events)
    assert all(event in output.shots[1].action_path for event in rain_facts().shots[1].required_events)
    assert [segment.name for shot in output.shots for segment in shot.generation_segments] == ["shot1", "shot2"]
    assert output.project["title"] == "雨夜回信"
    report = verify(rain_facts(), output)
    assert not [issue for issue in report.issues if issue.rule_id in {"MISSING_EVENT", "SEGMENT_MISSING"}]
    assert report.passed is True
    assert report.score == 100


def test_unsupported_or_forged_or_wrong_shot_events_are_not_injected() -> None:
    facts, output = rain_facts(), DirectorOutput.model_validate(base_output())
    result = _append_supported_events(output, facts, [
        {"shot_id": "shot1", "required_event": "右手拿着白色信封", "supported": True, "source_quote": "伪造引文"},
        {"shot_id": "shot1", "required_event": "抬头看向道路尽头", "supported": True, "source_quote": "抬头看向道路尽头"},
        {"shot_id": "shot1", "required_event": "不存在事件", "supported": True, "source_quote": "林舟"},
    ], SOURCE)
    assert "右手拿着白色信封" not in result.shots[0].action_path
    assert "抬头看向道路尽头" not in result.shots[0].action_path


def test_existing_exact_event_is_anchored_and_block_uses_source_order() -> None:
    facts, output = rain_facts(), DirectorOutput.model_validate(base_output())
    output.shots[0].action_path = "右手拿着白色信封"
    result = _append_supported_events(output, facts, supports(), SOURCE)
    assert result.shots[0].action_path.count("右手拿着白色信封") == 2
    additions = ["林舟站在雨夜公交站下", "右手拿着白色信封", "低头看信封", "镜头结束时仍然拿着信封"]
    positions = [result.shots[0].action_path.index(event) for event in additions]
    assert positions == sorted(positions)


def test_missing_event_and_wrong_dialogue_are_preserved_for_hard_rules() -> None:
    facts, payload = rain_facts(), base_output()
    payload["shots"][0]["video_prompt"] = "林舟站在站牌下，低头。"
    payload["shots"][1]["dialogue"] = [{"speaker": "林舟", "text": "我终于回来了。"}]
    response = {"director_output": payload, "required_event_support": []}
    output = parse_director_output_from_text("林舟站在站牌下，低头。林舟说：我终于回来了。", facts, MockClient(response))
    assert output.shots[1].dialogue[0].text == "我终于回来了。"
    rule_ids = {issue.rule_id for issue in verify(facts, output).issues}
    assert "MISSING_EVENT" in rule_ids
    assert "DIALOGUE_EXACT" in rule_ids


def test_existing_segments_are_preserved_with_exact_field_mapping() -> None:
    payload = base_output()
    segment = {"name": "custom", "recommended_generation_duration": 3, "first_frame_prompt": "首帧", "video_prompt": "视频", "negative_constraints": ["原顺序"]}
    payload["shots"][0]["generation_segments"] = [segment]
    response = {"director_output": payload, "required_event_support": supports()}
    output = parse_director_output_from_text(SOURCE, rain_facts(), MockClient(response))
    assert output.shots[0].generation_segments[0].model_dump() == segment
    generated = output.shots[1].generation_segments[0]
    assert (generated.name, generated.recommended_generation_duration, generated.first_frame_prompt, generated.video_prompt, generated.negative_constraints) == ("shot2", 3, "同一公交站，深蓝色夹克", "承接上一镜头，同一公交站，同一深蓝色夹克，右手仍拿同一封白色信封，抬眼望向远处", ["爆炸"])
