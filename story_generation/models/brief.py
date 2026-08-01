from __future__ import annotations

from pydantic import Field

from .common import Constraint, FieldProvenance, StrictModel


class CreativeBrief(StrictModel):
    premise: str
    format: str
    target_duration_s: float
    audience: str
    tone: list[str] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: dict[str, list[FieldProvenance]] = Field(default_factory=dict)
