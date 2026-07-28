from __future__ import annotations

import pytest

from creator_desktop.facts_review import apply_facts_edits
from creator_import.facts_extractor import extract_facts_from_text
from tests.test_facts_extractor import MockClient, facts_payload


def test_facts_review_edits_revalidate_model() -> None:
    facts = extract_facts_from_text("文本", MockClient([__import__("json").dumps(facts_payload(), ensure_ascii=False)]))
    edited = apply_facts_edits(facts, {"title": "新标题", "total_duration": "2", "character_ids": ["小雨"], "shots": [{"required_events": "撑伞", "forbidden_events": "爆炸", "dialogue": "小雨：原文台词"}]})
    assert edited.title == "新标题"
    assert edited.shots[0].exact_dialogue[0].text == "原文台词"


def test_facts_review_rejects_bad_dialogue_format() -> None:
    facts = extract_facts_from_text("文本", MockClient([__import__("json").dumps(facts_payload(), ensure_ascii=False)]))
    with pytest.raises(ValueError):
        apply_facts_edits(facts, {"title": "标题", "total_duration": "2", "character_ids": ["小雨"], "shots": [{"required_events": "", "forbidden_events": "", "dialogue": "没有说话人"}]})
