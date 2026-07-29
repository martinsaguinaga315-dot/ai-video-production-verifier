from __future__ import annotations

import json
import logging

import pytest

from creator_import.director_parser import parse_director_output_from_text
from creator_import.extraction_errors import ExtractionValidationError
from models import ProjectFacts
from rules import verify
from tests.test_director_event_anchoring import SOURCE, rain_facts, supports


class SequentialClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def request_json(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.responses.pop(0)


def compact_payload(*, unknown_character: bool = False) -> dict:
    characters = ["林舟"]
    if unknown_character:
        characters.append("陌生人")
    by_shot = {item["shot_id"]: item for item in supports()}
    return {
        "project": {"title": "模型错误标题"},
        "characters": [{"character_id": "林舟", "fixed_costume": "深蓝色夹克", "fixed_props": ["白色信封"]}],
        "props": [{"prop_id": "白色信封"}],
        "shots": [
            {"shot_id": "shot1", "characters": characters, "opening_state": "林舟站在雨夜公交站下", "action_path": "林舟低头看信封", "ending_state": "林舟仍然拿着信封", "required_event_support": [by_shot["shot1"]]},
            {"shot_id": "shot2", "characters": ["林舟"], "opening_state": "同一公交站", "action_path": "林舟抬头看向道路尽头", "ending_state": "林舟站在站牌下", "dialogue": [{"speaker": "林舟", "text": "我终于回来了。"}], "required_event_support": [by_shot["shot2"]]},
        ],
    }


def test_compact_draft_builds_local_fields_and_preserves_conflicts() -> None:
    payload = compact_payload(unknown_character=True)
    output = parse_director_output_from_text(SOURCE, rain_facts(), SequentialClient([json.dumps(payload, ensure_ascii=False)]))
    assert output.project == {"title": "雨夜回信", "total_duration": 6.0}
    assert [(shot.start_time, shot.end_time, shot.final_duration) for shot in output.shots] == [(0.0, 3.0, 3.0), (3.0, 6.0, 3.0)]
    assert output.shots[0].first_frame_prompt == output.shots[0].opening_state
    assert output.shots[0].video_prompt.startswith("固定事实事件（按导演原文顺序）：")
    assert "镜头结束时仍然拿着信封" in output.shots[0].video_prompt
    assert output.shots[0].generation_segments[0].name == "shot1"
    assert output.shots[1].dialogue[0].text == "我终于回来了。"
    assert "陌生人" in output.shots[0].characters
    assert {issue.rule_id for issue in verify(rain_facts(), output).issues} >= {"UNKNOWN_CHARACTER", "DIALOGUE_EXACT"}


def test_compact_response_accepts_markdown_and_retries_truncation_without_echoing_raw(caplog) -> None:
    secret = "PRIVATE_DIRECTOR_RESPONSE_MUST_NOT_LOG"
    good = "```json\n" + json.dumps(compact_payload(), ensure_ascii=False) + "\n```"
    client = SequentialClient(['{"shots": [' + secret, good])
    with caplog.at_level(logging.INFO):
        output = parse_director_output_from_text(SOURCE, rain_facts(), client)
    assert output.shots[0].shot_id == "shot1"
    assert len(client.calls) == 2
    assert secret not in caplog.text
    assert secret not in client.calls[1][1]


def test_compact_retry_is_limited_to_two_requests_and_reports_safe_error() -> None:
    secret = "PRIVATE_BROKEN_RESPONSE"
    client = SequentialClient(['{"bad": "' + secret, '{"still": "' + secret])
    with pytest.raises(ExtractionValidationError) as caught:
        parse_director_output_from_text(SOURCE, rain_facts(), client)
    assert len(client.calls) == 2
    assert secret not in str(caught.value)
    assert "返回内容不完整" in caught.value.details[0]


def test_five_shots_are_requested_in_two_fact_ordered_batches() -> None:
    facts = ProjectFacts.model_validate({
        "title": "五镜头", "total_duration": 15, "shot_count": 5, "characters": [], "props": [],
        "shots": [{"shot_id": f"S{index}", "start_time": (index - 1) * 3, "end_time": index * 3} for index in range(1, 6)],
    })
    first = {"shots": [{"shot_id": f"S{index}", "opening_state": "开场", "action_path": "动作"} for index in range(1, 5)]}
    second = {"shots": [{"shot_id": "S5", "opening_state": "开场", "action_path": "动作"}]}
    client = SequentialClient([json.dumps(first), json.dumps(second)])
    statuses: list[str] = []
    output = parse_director_output_from_text("五镜头文本", facts, client, status_callback=statuses.append)
    assert [shot.shot_id for shot in output.shots] == ["S1", "S2", "S3", "S4", "S5"]
    assert len(client.calls) == 2
    assert '"batch": "2/2"' in client.calls[1][1]
    assert statuses == ["正在解析导演方案：第1批，共2批", "正在解析导演方案：第2批，共2批"]


@pytest.mark.parametrize("shots, message", [
    ([{"shot_id": "shot1", "opening_state": "开场", "action_path": "动作"}], "缺少镜头ID"),
    ([{"shot_id": "shot1", "opening_state": "开场", "action_path": "动作"}, {"shot_id": "shot1", "opening_state": "开场", "action_path": "动作"}], "镜头ID重复"),
])
def test_compact_batch_rejects_missing_or_duplicate_ids(shots: list[dict], message: str) -> None:
    client = SequentialClient([json.dumps({"shots": shots}), json.dumps({"shots": shots})])
    with pytest.raises(ExtractionValidationError) as caught:
        parse_director_output_from_text(SOURCE, rain_facts(), client)
    assert message in caught.value.details[0]
