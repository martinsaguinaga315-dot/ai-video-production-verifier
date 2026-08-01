from __future__ import annotations

from pydantic import Field

from .common import FieldProvenance, FieldProvenanceMap, StrictModel


class PlotBeat(StrictModel):
    beat_id: str
    purpose: str
    conflict: str
    turn: str
    source_refs: list[str] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class PlotOutline(StrictModel):
    beats: list[PlotBeat] = Field(default_factory=list)
    ending: str
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)
