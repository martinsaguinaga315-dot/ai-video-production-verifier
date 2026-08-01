from __future__ import annotations

from pydantic import Field

from .common import FieldProvenance, FieldProvenanceMap, LocationDefinition, PropDefinition, StrictModel


class CharacterBible(StrictModel):
    character_id: str
    name: str
    role: str
    appearance: str
    goals: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class WorldBible(StrictModel):
    locations: list[LocationDefinition] = Field(default_factory=list)
    props: list[PropDefinition] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class StoryBible(StrictModel):
    logline: str
    theme: list[str] = Field(default_factory=list)
    characters: list[CharacterBible] = Field(default_factory=list)
    world: WorldBible
    canon_rules: list[str] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)
