from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.models import SourceKind, StoryboardDraft
from story_generation.services.story_validation_service import StoryValidationService


def test_minimal_ai_json_builds_valid_storyboard_draft():
    result = StoryboardBuilder().build({"shots": [{}]})

    assert isinstance(result, StoryboardDraft)
    assert result.storyboard_id.startswith("storyboard-generated-")
    assert result.scene_plan_id.startswith("scene-plan-generated-")
    assert result.shots[0].shot_id == "shot-001"
    assert result.shots[0].duration_s == 5.0


def test_builder_adds_generated_provenance_to_nested_models():
    result = StoryboardBuilder().build({"shots": [{}]})

    assert result.provenance.source_kind is SourceKind.GENERATED
    assert result.provenance.generation_request_id
    assert result.shots[0].provenance.generation_request_id == result.provenance.generation_request_id
    assert result.shots[0].opening_state.provenance.source_kind is SourceKind.GENERATED


def test_builder_maps_deepseek_duration_aliases_to_a_continuous_timeline():
    durations = [5, 5, 6, 6, 6, 6, 6, 6, 8, 6]
    result = StoryboardBuilder().build({
        "total_duration": 60,
        "shots": [{"shot_number": index + 1, "duration": duration} for index, duration in enumerate(durations)],
    })

    assert len(result.shots) == 10
    assert [shot.sequence for shot in result.shots] == list(range(1, 11))
    assert sum(shot.duration_s for shot in result.shots) == 60
    assert result.shots[0].start_time_s == 0
    assert result.shots[-1].end_time_s == 60
    assert all(current.start_time_s == previous.end_time_s for previous, current in zip(result.shots, result.shots[1:]))
    assert StoryValidationService().validate(result).status.value == "succeeded"


def test_builder_preserves_standard_timing_fields():
    result = StoryboardBuilder().build({
        "target_duration_s": 7,
        "shots": [{"sequence": 3, "start_time_s": 2, "end_time_s": 9, "duration_s": 7}],
    })

    shot = result.shots[0]
    assert (shot.sequence, shot.start_time_s, shot.end_time_s, shot.duration_s) == (3, 2, 9, 7)
