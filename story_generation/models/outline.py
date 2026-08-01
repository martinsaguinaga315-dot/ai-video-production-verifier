from __future__ import annotations

from pydantic import Field

from .common import CharacterRef, FieldProvenance, FieldProvenanceMap, StrictModel


class PlotBeat(StrictModel):
    beat_id: str
    sequence: int
    title: str
    purpose: str
    description: str
    characters: list[CharacterRef] = Field(default_factory=list)
    location_id: str
    required_events: list[str] = Field(default_factory=list)
    forbidden_events: list[str] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class PlotOutline(StrictModel):
    outline_id: str
    bible_id: str
    beats: list[PlotBeat] = Field(default_factory=list)
    target_duration_s: float
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)
