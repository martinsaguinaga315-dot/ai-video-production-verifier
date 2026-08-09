import pytest

from creator_desktop.creator_prompt_pack_store import CreatorPromptPackStore
from story_generation.models import PromptPackShot
from story_generation.platform_adapters import (
    PromptTargetPlatform,
    adapt_prompt_shot,
    get_platform_adapter,
)


@pytest.fixture
def canonical_shot():
    return PromptPackShot(
        shot_id="shot-001", scene_id="scene-001", sequence=1,
        first_frame_prompt="FIRST_FRAME_DISTINCT", end_frame_prompt="END_FRAME_DISTINCT",
        video_prompt="MOTION_CORE: subject moves left while camera tracks.",
        negative_prompt="NO_EXTRA_SUBJECT", continuity_notes="CONTINUITY_DISTINCT",
    )


def test_generic_preserves_every_canonical_prompt_field(canonical_shot):
    exported = adapt_prompt_shot(canonical_shot, "generic")
    for field in ("first_frame_prompt", "end_frame_prompt", "video_prompt", "negative_prompt", "continuity_notes"):
        assert getattr(exported, field) == getattr(canonical_shot, field)


def test_adaptation_is_deterministic_and_does_not_mutate_source(canonical_shot):
    before = canonical_shot.model_dump()
    first = adapt_prompt_shot(canonical_shot, "kling")
    second = adapt_prompt_shot(canonical_shot, "kling")
    assert first == second
    assert canonical_shot.model_dump() == before


@pytest.mark.parametrize("platform", ["kling", "jimeng", "veo"])
def test_field_preserving_platforms_keep_every_canonical_field_verbatim(canonical_shot, platform):
    exported = adapt_prompt_shot(canonical_shot, platform)
    for field in ("first_frame_prompt", "end_frame_prompt", "video_prompt", "negative_prompt", "continuity_notes"):
        assert getattr(exported, field) == getattr(canonical_shot, field)


def test_runway_is_motion_oriented_and_excludes_negative_from_video_prompt(canonical_shot):
    exported = adapt_prompt_shot(canonical_shot, "runway")
    assert exported.video_prompt == canonical_shot.video_prompt
    assert canonical_shot.first_frame_prompt not in exported.video_prompt
    assert canonical_shot.negative_prompt not in exported.video_prompt
    assert exported.negative_prompt == ""
    assert "正向" in exported.usage_notes
    assert "运动导向" in exported.usage_notes


def test_unknown_platform_is_an_explicit_error(canonical_shot):
    with pytest.raises(ValueError, match="Unknown prompt target platform"):
        adapt_prompt_shot(canonical_shot, "unknown")


def test_factory_maps_all_five_platforms():
    for platform in PromptTargetPlatform:
        assert get_platform_adapter(platform).platform is platform


def test_platform_export_cannot_be_persisted_in_the_canonical_prompt_pack_store(canonical_shot, tmp_path):
    platform_export = adapt_prompt_shot(canonical_shot, "runway")

    with pytest.raises(TypeError, match="canonical PromptPack"):
        CreatorPromptPackStore(tmp_path).save(platform_export)  # type: ignore[arg-type]
