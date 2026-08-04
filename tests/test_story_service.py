from story_generation.services.story_service import StoryService
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
