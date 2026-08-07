from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.models import GenerationStatus
from story_generation.services.creator_pipeline_service import CreatorPipelineService
from story_generation.services.story_validation_service import StoryValidationService


class MockStoryService:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.repairs = []

    def create_story(self, idea, style=None, goal=None, target_duration_s=60, aspect_ratio="16:9"):
        self.calls.append((idea, style, goal, target_duration_s, aspect_ratio))
        return self.payload

    def repair_storyboard(self, storyboard, issues, target_duration_s, parent_request_id=None):
        self.repairs.append((storyboard, issues, target_duration_s, parent_request_id))
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

    result = pipeline.create("进入地下接驳舱", "中国工业硬科幻", "生成分镜", target_duration_s=5)

    assert result.status is GenerationStatus.SUCCEEDED
    assert story_service.calls == [("进入地下接驳舱", "中国工业硬科幻", "生成分镜", 5, "16:9")]


def test_pipeline_passes_requested_duration_and_ratio_to_story_service():
    pipeline, story_service = build_pipeline({"target_duration_s": 30, "shots": [{"duration_s": 30}]})
    result = pipeline.create("创意", target_duration_s=30, aspect_ratio="9:16")
    assert result.status is GenerationStatus.SUCCEEDED
    assert story_service.calls == [("创意", None, None, 30, "9:16")]


def test_pipeline_preserves_a_600_second_duration_end_to_end():
    pipeline, story_service = build_pipeline({"target_duration_s": 600, "shots": [{"duration_s": 600}]})
    result = pipeline.create("长篇创意", target_duration_s=600, aspect_ratio="21:9")
    assert result.status is GenerationStatus.SUCCEEDED
    assert result.artifact.target_duration_s == 600
    assert sum(shot.duration_s for shot in result.artifact.shots) == 600
    assert story_service.calls == [("长篇创意", None, None, 600, "21:9")]


def test_pipeline_rejects_a_storyboard_with_the_wrong_requested_duration():
    pipeline, _ = build_pipeline({"target_duration_s": 60, "shots": [{"duration_s": 60}]})
    result = pipeline.create("创意", target_duration_s=30)
    assert result.status is GenerationStatus.FAILED
    assert any(item.path == "target_duration_s" for item in result.issues)


def test_pipeline_returns_failed_result_for_invalid_timeline():
    pipeline, _ = build_pipeline({
        "target_duration_s": 5,
        "shots": [{"start_time_s": 0, "end_time_s": 2, "duration_s": 5}],
    })

    result = pipeline.create("进入地下接驳舱")

    assert result.status is GenerationStatus.FAILED
    assert {item.code.value for item in result.issues} == {"DURATION_MISMATCH"}
