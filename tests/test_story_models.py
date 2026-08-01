from __future__ import annotations

import pytest
from pydantic import ValidationError

from datetime import datetime, timezone

from story_generation import models
from story_generation.models import CreativeBrief, FieldProvenance, GenerationResult, GenerationSettings, SourceKind, ThinkingMode

EXPECTED_MODEL_FIELDS = {
    "FieldProvenance": {"source_kind", "field_path", "source_path", "confirmed", "confirmed_at", "confirmed_by", "generation_request_id", "prior_sources"},
    "CreativeBrief": {"brief_id", "idea", "title", "language", "genre", "tone", "target_duration_s", "aspect_ratio", "target_platform", "target_audience", "visual_style", "dialogue_density", "ending_preference", "must_include", "forbidden_elements", "constraints", "provenance", "field_provenance"},
    "CharacterBible": {"character_id", "name", "role", "age_description", "appearance", "personality", "motivation", "internal_need", "external_goal", "relationships", "initial_state", "constraints", "provenance", "field_provenance"},
    "WorldBible": {"world_id", "time_period", "setting", "world_rules", "locations", "props", "constraints", "provenance", "field_provenance"},
    "StoryBible": {"bible_id", "brief_id", "theme", "premise", "characters", "world", "global_constraints", "provenance", "field_provenance"},
    "PlotBeat": {"beat_id", "sequence", "title", "purpose", "description", "characters", "location_id", "required_events", "forbidden_events", "provenance", "field_provenance"},
    "PlotOutline": {"outline_id", "bible_id", "beats", "target_duration_s", "provenance", "field_provenance"},
    "SceneDefinition": {"scene_id", "sequence", "title", "purpose", "location_id", "time_context", "target_duration_s", "characters", "props", "required_beats", "required_events", "forbidden_events", "opening_state", "ending_state", "notes", "provenance", "field_provenance"},
    "ScenePlan": {"scene_plan_id", "outline_id", "scenes", "target_duration_s", "provenance", "field_provenance"},
    "StoryboardShot": {"shot_id", "scene_id", "sequence", "start_time_s", "end_time_s", "duration_s", "location_id", "characters", "props", "opening_state", "action", "performance", "dialogue", "sound", "ending_state", "camera", "first_frame_prompt", "video_prompt", "negative_constraints", "continuity_refs", "required_events", "forbidden_events", "generation_segments", "provenance", "field_provenance"},
    "StoryboardDraft": {"storyboard_id", "scene_plan_id", "shots", "target_duration_s", "version", "provenance", "field_provenance"},
    "GenerationSettings": {"quality_mode", "model", "thinking_mode", "temperature", "max_tokens", "timeout_s", "stream", "max_retries"},
    "GenerationRequest": {"request_id", "stage_name", "input_artifact_type", "output_artifact_type", "settings", "created_at", "parent_request_id"},
    "GenerationMetadata": {"request_id", "stage_name", "model", "prompt_version", "status", "started_at", "completed_at", "usage", "repair_count", "parent_request_id", "finish_reason"},
    "GenerationIssue": {"code", "severity", "message", "path", "related_ids", "suggestion"},
    "GenerationResult": {"status", "artifact_type", "artifact", "issues", "metadata"},
}


def provenance() -> FieldProvenance:
    return FieldProvenance(source_kind=SourceKind.USER_EXPLICIT, field_path="/idea", source_path="idea")


@pytest.mark.parametrize(("name", "fields"), EXPECTED_MODEL_FIELDS.items())
def test_model_field_contracts(name: str, fields: set[str]) -> None:
    assert fields <= set(getattr(models, name).model_fields)


def test_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CreativeBrief.model_validate({
            "brief_id": "b", "idea": "A quiet reunion", "title": "t", "language": "zh", "target_duration_s": 30, "aspect_ratio": "16:9", "target_platform": "web", "target_audience": "general", "provenance": provenance().model_dump(), "unknown": True,
        })


def test_provenance_preserves_prior_ai_inference_on_confirmation() -> None:
    inferred = FieldProvenance(source_kind=SourceKind.AI_INFERENCE, field_path="/idea", generation_request_id="req-1")
    confirmed = FieldProvenance(
        source_kind=SourceKind.USER_CONFIRMED, field_path="/idea", confirmed=True, confirmed_by="user", confirmed_at=datetime.now(timezone.utc),
        prior_sources=[inferred],
    )
    assert confirmed.prior_sources[0].source_kind is SourceKind.AI_INFERENCE


def test_provenance_rejects_invalid_confirmation_and_paths() -> None:
    with pytest.raises(ValidationError):
        FieldProvenance(source_kind=SourceKind.USER_CONFIRMED, field_path="idea", confirmed=True)
    with pytest.raises(ValidationError):
        FieldProvenance(source_kind=SourceKind.AI_INFERENCE, field_path="/idea", confirmed=True)


def test_generation_settings_accepts_explicit_thinking_configuration() -> None:
    settings = GenerationSettings(
        quality_mode="quality", model="deepseek-v4-pro", thinking_mode=ThinkingMode.HIGH,
        temperature=None, max_tokens=5000, timeout_s=45,
    )
    assert settings.thinking_mode is ThinkingMode.HIGH


def test_generation_result_rejects_non_json_artifact() -> None:
    with pytest.raises(ValidationError):
        GenerationResult(status="succeeded", artifact_type="creative_brief", artifact=object())
