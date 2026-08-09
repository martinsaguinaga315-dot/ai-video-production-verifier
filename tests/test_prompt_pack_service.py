import pytest

from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.services.prompt_pack_service import PromptPackService


def build_storyboard(shots):
    return StoryboardBuilder().build({"storyboard_id": "storyboard-test", "target_duration_s": 12, "shots": shots})


def shot(sequence, opening="At the closed hatch.", ending="At the control console."):
    return {
        "shot_id": f"shot-{sequence:03d}", "scene_id": "scene-001", "sequence": sequence, "duration_s": 6,
        "location_id": "industrial cabin", "characters": [{"character_id": "operator"}], "props": ["physical switch"],
        "opening_state": {"description": opening}, "action": "Move right and operate the control console.",
        "performance": "focused", "ending_state": {"description": ending}, "camera": "left-rear medium tracking shot",
        "first_frame_prompt": "operator beside the closed hatch", "video_prompt": "track the operator moving right",
        "negative_constraints": ["no extra operator"], "continuity_refs": ["keep the hatch closed"],
        "required_events": ["hand reaches physical switch"], "forbidden_events": ["hatch opens"],
    }


def test_generator_uses_opening_and_ending_states_without_collapsing_frames():
    pack = PromptPackService().generate(build_storyboard([shot(1)]))
    prompt = pack.shots[0]
    assert "At the closed hatch." in prompt.first_frame_prompt
    assert "At the control console." in prompt.end_frame_prompt
    assert prompt.first_frame_prompt != prompt.end_frame_prompt


def test_video_prompt_contains_action_camera_duration_and_end_state():
    prompt = PromptPackService().generate(build_storyboard([shot(1)])).shots[0].video_prompt
    for expected in ("Move right", "left-rear medium tracking shot", "镜头持续 6 秒", "At the control console."):
        assert expected in prompt


def test_negative_and_continuity_use_storyboard_constraints():
    prompt = PromptPackService().generate(build_storyboard([shot(1)])).shots[0]
    assert "no extra operator" in prompt.negative_prompt
    assert "hatch opens" in prompt.negative_prompt
    assert "keep the hatch closed" in prompt.continuity_notes


def test_selected_shots_keep_sequence_order_and_unknown_ids_fail():
    storyboard = build_storyboard([shot(2), shot(1)])
    pack = PromptPackService().generate(storyboard, shot_ids=["shot-002", "shot-001"])
    assert [item.sequence for item in pack.shots] == [1, 2]
    with pytest.raises(ValueError, match="Unknown shot_id"):
        PromptPackService().generate(storyboard, shot_ids=["not-a-shot"])


def test_empty_storyboard_generates_an_empty_stable_pack():
    pack = PromptPackService().generate(build_storyboard([]))
    assert pack.shots == []
    assert pack.prompt_pack_id == "prompt-pack-storyboard-test-v1"


def test_default_is_chinese_and_empty_optional_fields_are_omitted():
    source = shot(1)
    source.update({"characters": [], "props": [], "continuity_refs": [], "required_events": [], "forbidden_events": []})
    prompt = PromptPackService().generate(build_storyboard([source]))
    assert prompt.output_language == "zh-CN"
    assert "First frame" not in prompt.shots[0].first_frame_prompt
    assert "At location" not in prompt.shots[0].first_frame_prompt
    assert "none specified" not in prompt.shots[0].first_frame_prompt
    assert "人物：未指定" not in prompt.shots[0].continuity_notes
    assert "道具：未指定" not in prompt.shots[0].continuity_notes


def test_english_template_remains_available():
    prompt = PromptPackService().generate(build_storyboard([shot(1)]), output_language="en")
    assert prompt.output_language == "en"
    assert "At industrial cabin" in prompt.shots[0].first_frame_prompt
    assert "Duration: 6 seconds" in prompt.shots[0].video_prompt


def test_placeholder_locations_and_states_are_omitted_without_harming_real_values():
    source = shot(1, opening="State unspecified.", ending="State unspecified")
    source["location_id"] = "location-generated-001"
    prompt = PromptPackService().generate(build_storyboard([source]))
    rendered = "\n".join(prompt.shots[0].model_dump().values() if False else [
        prompt.shots[0].first_frame_prompt, prompt.shots[0].end_frame_prompt,
        prompt.shots[0].video_prompt, prompt.shots[0].continuity_notes,
    ])
    for prohibited in ("location-generated-", "State unspecified", "none specified", "At location"):
        assert prohibited not in rendered
    source["location_id"] = "L-7 external docking chamber"
    real_prompt = PromptPackService().generate(build_storyboard([source]), output_language="en")
    assert "At L-7 external docking chamber" in real_prompt.shots[0].first_frame_prompt
