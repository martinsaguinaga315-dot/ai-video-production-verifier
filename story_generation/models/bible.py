from __future__ import annotations

from pydantic import Field

from .common import Constraint, FieldProvenance, FieldProvenanceMap, LocationDefinition, PropDefinition, StrictModel


class CharacterBible(StrictModel):
    character_id: str
    name: str
    role: str
    age_description: str
    appearance: str
    personality: list[str] = Field(default_factory=list)
    motivation: str = ""
    internal_need: str = ""
    external_goal: str = ""
    relationships: dict[str, str] = Field(default_factory=dict)
    initial_state: str = ""
    constraints: list[Constraint] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class WorldBible(StrictModel):
    world_id: str
    time_period: str
    setting: str
    world_rules: list[str] = Field(default_factory=list)
    locations: list[LocationDefinition] = Field(default_factory=list)
    props: list[PropDefinition] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class StoryBible(StrictModel):
    bible_id: str
    brief_id: str
    theme: list[str] = Field(default_factory=list)
    premise: str
    characters: list[CharacterBible] = Field(default_factory=list)
    world: WorldBible
    global_constraints: list[Constraint] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)
