from __future__ import annotations

from pydantic import Field

from .common import CharacterRef, FieldProvenance, FieldProvenanceMap, ShotState, StrictModel


class SceneDefinition(StrictModel):
    scene_id: str
    sequence: int
    title: str
    purpose: str
    location_id: str
    time_context: str
    target_duration_s: float
    characters: list[CharacterRef] = Field(default_factory=list)
    props: list[str] = Field(default_factory=list)
    required_beats: list[str] = Field(default_factory=list)
    required_events: list[str] = Field(default_factory=list)
    forbidden_events: list[str] = Field(default_factory=list)
    opening_state: ShotState
    ending_state: ShotState
    notes: str = ""
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class ScenePlan(StrictModel):
    scenes: list[SceneDefinition] = Field(default_factory=list)
    total_duration_s: float
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)
