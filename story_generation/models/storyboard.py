from __future__ import annotations

from pydantic import Field

from .common import CharacterRef, DialogueLineDraft, FieldProvenance, FieldProvenanceMap, ShotState, StrictModel


class StoryboardShot(StrictModel):
    shot_id: str
    scene_id: str
    sequence: int
    start_time_s: float
    end_time_s: float
    duration_s: float
    location_id: str
    characters: list[CharacterRef] = Field(default_factory=list)
    props: list[str] = Field(default_factory=list)
    opening_state: ShotState
    action: str
    performance: str
    dialogue: list[DialogueLineDraft] = Field(default_factory=list)
    sound: list[str] = Field(default_factory=list)
    ending_state: ShotState
    camera: str
    first_frame_prompt: str
    video_prompt: str
    negative_constraints: list[str] = Field(default_factory=list)
    continuity_refs: list[str] = Field(default_factory=list)
    required_events: list[str] = Field(default_factory=list)
    forbidden_events: list[str] = Field(default_factory=list)
    generation_segments: list[str] = Field(default_factory=list)
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)


class StoryboardDraft(StrictModel):
    shots: list[StoryboardShot] = Field(default_factory=list)
    version: int
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)
