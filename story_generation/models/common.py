from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceKind(StrEnum):
    USER_EXPLICIT = "user_explicit"
    AI_INFERENCE = "ai_inference"
    USER_CONFIRMED = "user_confirmed"
    GENERATED = "generated"
    VERIFICATION_RESULT = "verification_result"
    AUTO_REPAIR = "auto_repair"


class FieldProvenance(StrictModel):
    source_kind: SourceKind
    source_path: str = ""
    confirmed: bool = False
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None
    generation_request_id: str | None = None
    prior_sources: list["FieldProvenance"] = Field(default_factory=list)


class Constraint(StrictModel):
    constraint_id: str
    text: str
    scope: str
    authoritative: bool = False
    provenance: FieldProvenance


class CharacterRef(StrictModel):
    character_id: str
    provenance: FieldProvenance


class LocationDefinition(StrictModel):
    location_id: str
    name: str
    description: str
    constraints: list[Constraint] = Field(default_factory=list)
    provenance: FieldProvenance


class PropDefinition(StrictModel):
    prop_id: str
    name: str
    owner_character_id: str | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    provenance: FieldProvenance


class DialogueLineDraft(StrictModel):
    speaker: CharacterRef
    text: str
    provenance: FieldProvenance


class ShotState(StrictModel):
    description: str
    character_states: dict[str, str] = Field(default_factory=dict)
    prop_states: dict[str, str] = Field(default_factory=dict)
    provenance: FieldProvenance
