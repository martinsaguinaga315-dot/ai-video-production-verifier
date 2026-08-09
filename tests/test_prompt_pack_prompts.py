from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.prompts.prompt_pack_prompts import SYSTEM_PROMPT, build_user_prompt


def test_prompt_contains_storyboard_facts_and_neighbor_context():
    storyboard = StoryboardBuilder().build({"target_duration_s": 12, "shots": [
        {"sequence": 1, "duration_s": 6, "camera": "static", "action": "start", "performance": "calm", "first_frame_prompt": "one", "video_prompt": "one"},
        {"sequence": 2, "duration_s": 6, "camera": "track", "action": "finish", "performance": "focused", "first_frame_prompt": "two", "video_prompt": "two", "negative_constraints": ["no extras"], "forbidden_events": ["no jump"]},
    ]})
    prompt = build_user_prompt(current=storyboard.shots[1], previous=storyboard.shots[0], next_shot=None, output_language="zh-CN", generation_target="generic")
    assert "specialist AI video director" in SYSTEM_PROMPT
    for expected in ("previous_shot", "current_shot", "opening_state", "ending_state", "duration_s", "camera", "no extras", "no jump", "zh-CN"):
        assert expected in prompt


def test_system_prompt_requires_the_exact_production_shot_schema():
    for field in ("shot_id", "first_frame_prompt", "end_frame_prompt", "video_prompt", "negative_prompt", "continuity_notes"):
        assert field in SYSTEM_PROMPT
    assert "Do not return input data" in SYSTEM_PROMPT


def test_system_prompt_sets_production_visual_execution_requirements():
    for expected in (
        "production prompt engineer",
        "composition", "camera angle and height", "lighting direction", "motion pacing",
        "current_shot is the highest-priority source", "previous_shot", "next_shot",
        "current_shot.duration_s", "FACT PRESERVATION", "Do not invent new characters, props, locations",
        "NEGATIVE PROMPT", "CONTINUITY NOTES",
    ):
        assert expected in SYSTEM_PROMPT


def test_system_prompt_requires_start_end_and_video_alignment():
    for expected in (
        "must exactly align with the start state of video_prompt",
        "must exactly align with the end state of video_prompt",
        "Its start state must align with first_frame_prompt",
        "its end state must align with end_frame_prompt",
        "first-frame start facts", "next-shot handoff state",
    ):
        assert expected in SYSTEM_PROMPT


def test_system_prompt_preserves_facts_and_requires_freeze_frame_end_state():
    for expected in (
        "Do not add narrative inference", "made up their mind",
        "Do not add unprovided environmental events", "lamp flickering or dimming",
        "freeze-frame specification", "subject's frame occupancy",
        "where each relevant hand stops", "where each relevant prop stops",
    ):
        assert expected in SYSTEM_PROMPT


def test_system_prompt_requires_specific_negative_and_continuity_locks():
    for expected in (
        "face drift", "age changes", "hairstyle changes", "wardrobe changes",
        "finger errors or hand deformation", "prop disappearance or position jumps",
        "wrong shot size", "wrong camera direction", "focus drifting to the background",
        "multi-shot feeling", "approximate age impression", "hairstyle",
        "existing wardrobe", "important props", "current action end state",
    ):
        assert expected in SYSTEM_PROMPT
