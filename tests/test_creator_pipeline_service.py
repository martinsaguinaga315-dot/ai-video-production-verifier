from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.models import GenerationStatus
from story_generation.services.creator_pipeline_service import CreatorPipelineService
from story_generation.services.story_validation_service import StoryValidationService


class MockStoryService:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create_story(self, idea, style=None, goal=None):
        self.calls.append((idea, style, goal))
        return self.payload


def build_pipeline(payload):
    story_service = MockStoryService(payload)
    pipeline = CreatorPipelineService(
        story_service=story_service,
        storyboard_builder=StoryboardBuilder(),
        validation_service=StoryValidationService(),
    )
    return pipeline, story_service


def test_pipeline_returns_succeeded_result_and_passes_story_inputs():
    pipeline, story_service = build_pipeline({"target_duration_s": 5, "shots": [{}]})

    result = pipeline.create("进入地下接驳舱", "中国工业硬科幻", "生成分镜")

    assert result.status is GenerationStatus.SUCCEEDED
    assert story_service.calls == [("进入地下接驳舱", "中国工业硬科幻", "生成分镜")]


def test_pipeline_returns_failed_result_for_invalid_timeline():
    pipeline, _ = build_pipeline({
        "target_duration_s": 5,
        "shots": [{"start_time_s": 0, "end_time_s": 2, "duration_s": 5}],
    })

    result = pipeline.create("进入地下接驳舱")

    assert result.status is GenerationStatus.FAILED
    assert {item.code.value for item in result.issues} == {"DURATION_MISMATCH"}
