from __future__ import annotations

import pytest
from pydantic import ValidationError

from story_generation.models import (
    CreativeBrief,
    FieldProvenance,
    FieldProvenanceMap,
    GenerationSettings,
    SourceKind,
    ThinkingMode,
)


def provenance() -> FieldProvenance:
    return FieldProvenance(source_kind=SourceKind.USER_EXPLICIT, source_path="idea")


def test_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CreativeBrief.model_validate({
            "premise": "A quiet reunion", "format": "short", "target_duration_s": 30,
            "audience": "general", "provenance": provenance().model_dump(), "unknown": True,
        })


def test_provenance_preserves_prior_ai_inference_on_confirmation() -> None:
    inferred = FieldProvenance(source_kind=SourceKind.AI_INFERENCE, generation_request_id="req-1")
    confirmed = FieldProvenance(
        source_kind=SourceKind.USER_CONFIRMED, confirmed=True, confirmed_by="user",
        prior_sources=[inferred],
    )
    assert confirmed.prior_sources[0].source_kind is SourceKind.AI_INFERENCE


def test_field_provenance_is_strict_and_retains_field_history() -> None:
    history = FieldProvenanceMap(fields={"premise": [provenance()]})
    assert history.fields["premise"][0].source_path == "idea"
    with pytest.raises(ValidationError):
        FieldProvenanceMap.model_validate({"fields": {}, "unknown": True})


def test_generation_settings_accepts_explicit_thinking_configuration() -> None:
    settings = GenerationSettings(
        model="deepseek-v4-pro", thinking_mode=ThinkingMode.HIGH,
        temperature=None, max_tokens=5000, timeout_s=45,
    )
    assert settings.thinking_mode is ThinkingMode.HIGH
