from story_generation.services.story_service import StoryService
import pytest

from story_generation.generators.creator_generator import CreatorGenerator
from story_generation.models import ArtifactType


def test_story_service_create_request():

    generator = CreatorGenerator()

    service = StoryService(
        generator=generator
    )

    result = service.create_story_request(
        idea="047进入地下七层外部接驳舱",
        style="中国工业硬科幻",
        goal="生成AI视频分镜",
    )

    assert result.stage_name == "storyboard_generation"
    assert result.input_artifact_type == ArtifactType.CREATIVE_BRIEF
    assert result.output_artifact_type == ArtifactType.STORYBOARD_DRAFT
    assert service._build_brief("创意", target_duration_s=30, aspect_ratio="9:16").target_duration_s == 30
    assert service._build_brief("创意", target_duration_s=30, aspect_ratio="9:16").aspect_ratio == "9:16"


def test_story_service_preserves_a_120_second_request():
    brief = StoryService(generator=CreatorGenerator())._build_brief("创意", target_duration_s=120, aspect_ratio="21:9")
    assert brief.target_duration_s == 120
    assert brief.aspect_ratio == "21:9"


@pytest.mark.parametrize("duration", [347, 600])
def test_story_service_preserves_arbitrary_integer_duration(duration):
    brief = StoryService(generator=CreatorGenerator())._build_brief("创意", target_duration_s=duration)
    assert brief.target_duration_s == duration
