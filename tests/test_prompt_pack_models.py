from story_generation.models import PromptPack, PromptPackShot


def test_prompt_pack_json_round_trip():
    pack = PromptPack(
        prompt_pack_id="prompt-pack-storyboard-1-v1",
        storyboard_id="storyboard-1",
        storyboard_version=1,
        generation_target="generic",
        shots=[PromptPackShot(
            shot_id="shot-001", scene_id="scene-001", sequence=1,
            first_frame_prompt="opening", end_frame_prompt="ending", video_prompt="motion",
            negative_prompt="no additions", continuity_notes="keep continuity",
        )],
    )
    assert PromptPack.model_validate_json(pack.model_dump_json()) == pack
    assert pack.output_language == "zh-CN"


def test_prompt_pack_shot_rejects_unknown_fields():
    data = {"shot_id": "shot-001", "scene_id": "scene-001", "sequence": 1, "first_frame_prompt": "a", "end_frame_prompt": "b", "video_prompt": "c", "negative_prompt": "d", "continuity_notes": "e", "unexpected": True}
    try:
        PromptPackShot.model_validate(data)
    except ValueError:
        pass
    else:
        raise AssertionError("PromptPackShot must remain strict")
