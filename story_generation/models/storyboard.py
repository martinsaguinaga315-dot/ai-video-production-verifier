from __future__ import annotations

from pydantic import Field, model_validator

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

    @model_validator(mode="after")
    def _validate_times(self) -> "StoryboardShot":
        if self.start_time_s < 0 or self.end_time_s < 0 or self.duration_s <= 0:
            raise ValueError("shot times must be non-negative and duration positive")
        return self


class StoryboardDraft(StrictModel):
    storyboard_id: str
    scene_plan_id: str
    shots: list[StoryboardShot] = Field(default_factory=list)
    target_duration_s: float
    version: int
    provenance: FieldProvenance
    field_provenance: FieldProvenanceMap = Field(default_factory=FieldProvenanceMap)

    @model_validator(mode="after")
    def _validate_version(self) -> "StoryboardDraft":
        if self.version < 1 or self.target_duration_s <= 0:
            raise ValueError("version must be positive")
        return self
