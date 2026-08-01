from __future__ import annotations

from pydantic import Field, model_validator

from .common import Constraint, FieldProvenance, FieldProvenanceMap, StrictModel


class CreativeBrief(StrictModel):
    brief_id: str
    idea: str
    title: str
    language: str
    genre: list[str] = Field(default_factory=list)
    tone: list[str] = Field(default_factory=list)
    target_duration_s: float
    aspect_ratio: str
    target_platform: str
    target_audience: str
    visual_style: list[str] = Field(default_factory=list)
    dialogue_density: str = ""
    ending_preference: str = ""
    must_include: list[str] = Field(default_factory=list)
    forbidden_elements: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)

    @model_validator(mode="after")
    def _duration_positive(self) -> "CreativeBrief":
        if self.target_duration_s <= 0: raise ValueError("target_duration_s must be positive")
        return self
