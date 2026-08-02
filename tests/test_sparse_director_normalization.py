from __future__ import annotations

import json

import pytest

from creator_import.director_parser import (
    normalize_shot_generation_fields,
    parse_director_output_from_text,
)
from creator_import.extraction_errors import ExtractionValidationError
from tests.test_director_event_anchoring import MockClient, SOURCE, base_output, rain_facts, supports


def test_normalizes_empty_first_frame_video_and_zero_duration() -> None:
    shot = {"shot_id": "S01", "start_time": 0, "end_time": 4, "final_duration": 0,
            "opening_state": "人物站在门口", "action_path": "人物抬头", "first_frame_prompt": "", "video_prompt": "", "negative_constraints": ["爆炸"]}
    result = normalize_shot_generation_fields(shot)
    assert result["final_duration"] == 4
    assert result["first_frame_prompt"] == "人物站在门口"
    assert result["video_prompt"] == "人物抬头"


def test_video_can_use_existing_opening_ending_and_dialogue_only() -> None:
    shot = {"shot_id": "S01", "start_time": 0, "end_time": 2, "final_duration": 2,
            "opening_state": "人物坐着", "action_path": "", "performance": "", "ending_state": "人物起身",
            "dialogue": [{"speaker": "甲", "text": "你好"}], "first_frame_prompt": "首帧", "video_prompt": ""}
    assert normalize_shot_generation_fields(shot)["video_prompt"] == "人物坐着\n人物起身\n甲：你好"


def test_sparse_realistic_output_becomes_complete_director_output() -> None:
    payload = base_output()
    for shot in payload["shots"]:
        shot["first_frame_prompt"] = ""
        shot["video_prompt"] = ""
        shot["generation_segments"] = []
    payload["shots"][0]["final_duration"] = 0
    response = {"director_output": payload, "required_event_support": supports()}
    output = parse_director_output_from_text(SOURCE, rain_facts(), MockClient(response))
    assert output.shots[0].final_duration == 3
    assert all(shot.first_frame_prompt and shot.video_prompt and shot.generation_segments for shot in output.shots)
    assert output.shots[0].generation_segments[0].name == "shot1"


def test_sparse_errors_name_the_actual_missing_source() -> None:
    with pytest.raises(ExtractionValidationError) as first_error:
        normalize_shot_generation_fields({"shot_id": "S01", "start_time": 0, "end_time": 2, "final_duration": 2, "first_frame_prompt": "", "opening_state": ""})
    assert "first_frame_prompt和opening_state均为空" in first_error.value.details[0]
    with pytest.raises(ExtractionValidationError) as video_error:
        normalize_shot_generation_fields({"shot_id": "S01", "start_time": 0, "end_time": 2, "final_duration": 2, "first_frame_prompt": "首帧", "video_prompt": "", "action_path": "", "opening_state": "", "ending_state": ""})
    assert "video_prompt、action_path、opening_state和ending_state均为空" in video_error.value.details[0]
    with pytest.raises(ExtractionValidationError) as duration_error:
        normalize_shot_generation_fields({"shot_id": "S01", "start_time": 2, "end_time": 2, "final_duration": 0})
    assert "end_time不大于start_time" in duration_error.value.details[0]
