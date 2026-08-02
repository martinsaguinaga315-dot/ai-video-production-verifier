from __future__ import annotations

import json

from creator_import.director_parser import parse_director_output_from_text
from creator_import.facts_extractor import extract_facts_from_text
from tests.test_facts_extractor import MockClient, facts_payload


def director_payload() -> dict:
    return {
        "project": {"title": "雨夜"},
        "characters": [{"character_id": "小雨", "fixed_costume": "蓝外套", "fixed_props": ["伞"]}],
        "props": [{"prop_id": "伞", "owner": "小雨"}],
        "shots": [{"shot_id": "S01", "start_time": 0, "end_time": 2, "final_duration": 2,
                    "characters": ["小雨"], "opening_state": "小雨撑伞", "action_path": "小雨撑伞",
                    "ending_state": "小雨撑伞", "dialogue": [{"speaker": "小雨", "text": "别等我。"}],
                    "generation_segments": [{"name": "S01", "recommended_generation_duration": 2,
                                             "first_frame_prompt": "小雨撑伞", "video_prompt": "小雨撑伞"}]}],
    }


def test_director_parser_uses_facts_constraints_in_prompt() -> None:
    facts = extract_facts_from_text("文本", MockClient([json.dumps(facts_payload(), ensure_ascii=False)]))
    client = MockClient([json.dumps(director_payload(), ensure_ascii=False)])
    output = parse_director_output_from_text("分镜", facts, client)
    assert output.shots[0].shot_id == "S01"
    assert "小雨" in client.calls[0][1]


def test_director_conflict_is_retained_for_verifier() -> None:
    facts = extract_facts_from_text("文本", MockClient([json.dumps(facts_payload(), ensure_ascii=False)]))
    payload = director_payload()
    payload["shots"][0]["characters"] = ["陌生人"]
    output = parse_director_output_from_text("冲突原文", facts, MockClient([json.dumps(payload, ensure_ascii=False)]))
    assert output.shots[0].characters == ["陌生人"]
