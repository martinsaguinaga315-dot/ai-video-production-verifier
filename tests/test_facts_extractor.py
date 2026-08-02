from __future__ import annotations

import json

import pytest

from creator_import.extraction_errors import ExtractionValidationError
from creator_import.facts_extractor import extract_facts_from_text


class MockClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def request_json(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.responses.pop(0)


def facts_payload() -> dict:
    return {
        "title": "雨夜", "total_duration": 2, "shot_count": 1,
        "characters": [{"character_id": "小雨", "fixed_costume_terms": ["蓝外套"]}],
        "props": [{"prop_id": "伞", "owner": "小雨"}],
        "shots": [{"shot_id": "S01", "start_time": 0, "end_time": 2,
                    "required_events": ["小雨撑伞"], "exact_dialogue": [{"speaker": "小雨", "text": "别等我。"}]}],
        "global_forbidden_events": ["爆炸"],
    }


def test_facts_response_validates_and_keeps_exact_dialogue() -> None:
    client = MockClient([json.dumps(facts_payload(), ensure_ascii=False)])
    facts = extract_facts_from_text("小雨说：别等我。", client)
    assert facts.title == "雨夜"
    assert facts.shots[0].exact_dialogue[0].text == "别等我。"
    assert "有人" not in [character.character_id for character in facts.characters]


def test_missing_fields_enters_repair_and_stops_after_two_repairs() -> None:
    fixed = json.dumps(facts_payload(), ensure_ascii=False)
    client = MockClient(['{"title":"缺字段"}', fixed])
    facts = extract_facts_from_text("文本", client)
    assert facts.shot_count == 1
    assert len(client.calls) == 2


def test_unrepairable_facts_fails_after_two_repairs() -> None:
    client = MockClient(['{}', '{}', '{}'])
    with pytest.raises(ExtractionValidationError) as caught:
        extract_facts_from_text("文本", client)
    assert "自动结构化失败" in str(caught.value)
    assert len(client.calls) == 3
