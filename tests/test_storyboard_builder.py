from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.models import SourceKind, StoryboardDraft


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
