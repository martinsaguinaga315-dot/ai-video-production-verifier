from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.models import GenerationStatus
from story_generation.services.story_validation_service import StoryValidationService


def test_valid_storyboard_returns_success():
    storyboard = StoryboardBuilder().build({"target_duration_s": 5, "shots": [{}]})

    result = StoryValidationService().validate(storyboard)

    assert result.status is GenerationStatus.SUCCEEDED
    assert result.artifact is storyboard
    assert result.issues == []


def test_invalid_timeline_returns_issues():
    storyboard = StoryboardBuilder().build({
        "target_duration_s": 5,
        "shots": [{"start_time_s": 0, "end_time_s": 2, "duration_s": 5}],
    })

    result = StoryValidationService().validate(storyboard)

    assert result.status is GenerationStatus.FAILED
    assert {item.code.value for item in result.issues} == {"DURATION_MISMATCH"}
