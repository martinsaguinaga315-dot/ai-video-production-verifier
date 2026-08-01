from __future__ import annotations

from datetime import datetime
from math import isfinite
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def _validate_contract_scalars(self) -> "StrictModel":
        for name in self.__class__.model_fields:
            value = getattr(self, name)
            if (name == "sequence" or name.endswith("_id")) and isinstance(value, str) and not value:
                raise ValueError(f"{name} must not be empty")
            if name == "sequence" and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                raise ValueError("sequence must be a positive integer")
            if isinstance(value, float) and not isfinite(value):
                raise ValueError(f"{name} must be finite")
        return self


class SourceKind(StrEnum):
    USER_EXPLICIT = "user_explicit"
    AI_INFERENCE = "ai_inference"
    USER_CONFIRMED = "user_confirmed"
    GENERATED = "generated"
    VERIFICATION_RESULT = "verification_result"
    AUTO_REPAIR = "auto_repair"


class FieldProvenance(StrictModel):
    source_kind: SourceKind
    field_path: str
    source_path: str = ""
    confirmed: bool = False
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None
    generation_request_id: str | None = None
    prior_sources: list["FieldProvenance"] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_confirmation(self) -> "FieldProvenance":
        if not self.field_path.startswith("/") or len(self.field_path) == 1:
            raise ValueError("field_path must be a non-empty JSON Pointer")
        if self.confirmed_at is not None and self.confirmed_at.tzinfo is None:
            raise ValueError("confirmed_at must include a timezone")
        if self.source_kind is SourceKind.USER_CONFIRMED and (not self.confirmed or self.confirmed_at is None or not self.confirmed_by):
            raise ValueError("user-confirmed provenance needs confirmation metadata")
        if self.source_kind is SourceKind.AI_INFERENCE and self.confirmed:
            raise ValueError("AI inference must not be marked confirmed")
        if any(source is self for source in self.prior_sources):
            raise ValueError("prior_sources must not directly reference itself")
        return self


class FieldProvenanceMap(StrictModel):
    """Provenance histories keyed by a concrete field name or field path."""

    fields: dict[str, list[FieldProvenance]] = Field(default_factory=dict)


class Constraint(StrictModel):
    constraint_id: str
    text: str
    scope: str
    authoritative: bool = False
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class CharacterRef(StrictModel):
    character_id: str
    provenance: FieldProvenance


class LocationDefinition(StrictModel):
    location_id: str
    name: str
    description: str
    visual_features: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class PropDefinition(StrictModel):
    prop_id: str
    name: str
    description: str = ""
    initial_owner_id: str | None = None
    initial_location_id: str | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class DialogueLineDraft(StrictModel):
    speaker_id: str
    text: str
    emotion: str = ""
    delivery: str = ""
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class ShotState(StrictModel):
    description: str
    character_states: dict[str, str] = Field(default_factory=dict)
    prop_states: dict[str, str] = Field(default_factory=dict)
    environment_state: str = ""
    continuity_notes: list[str] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)
