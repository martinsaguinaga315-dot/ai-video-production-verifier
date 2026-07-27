from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DialogueLine(BaseModel):
    speaker: str
    text: str


class ExpectedShot(BaseModel):
    model_config = ConfigDict(extra="allow")

    shot_id: str
    start_time: float
    end_time: float
    required_events: list[str] = Field(default_factory=list)
    forbidden_events: list[str] = Field(default_factory=list)
    exact_dialogue: list[DialogueLine] = Field(default_factory=list)


class CharacterLock(BaseModel):
    """
    Facts-layer character lock.

    fixed_appearance_terms:
        Cross-shot identity and appearance facts such as age, hair, face,
        body type, or other explicitly locked visual traits.

    initial_state_terms:
        Explicit opening-state traits that may be temporary, such as wet hair,
        blood, dirt, a wound, or an object already held at the beginning.

    Existing facts.json files remain valid because all new fields have defaults.
    """

    model_config = ConfigDict(extra="allow")

    character_id: str
    fixed_appearance_terms: list[str] = Field(default_factory=list)
    initial_state_terms: list[str] = Field(default_factory=list)
    forbidden_appearance_terms: list[str] = Field(default_factory=list)
    fixed_costume_terms: list[str] = Field(default_factory=list)
    forbidden_costume_terms: list[str] = Field(default_factory=list)
    fixed_props: list[str] = Field(default_factory=list)


class PropLock(BaseModel):
    model_config = ConfigDict(extra="allow")

    prop_id: str
    owner: str = ""
    forbidden_terms: list[str] = Field(default_factory=list)


class ProjectFacts(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    total_duration: float
    shot_count: int
    characters: list[CharacterLock]
    props: list[PropLock]
    shots: list[ExpectedShot]
    global_forbidden_events: list[str] = Field(default_factory=list)


class GenerationSegment(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    recommended_generation_duration: float | None = None
    first_frame_prompt: str = ""
    video_prompt: str = ""
    negative_constraints: list[str] = Field(default_factory=list)


class OutputShot(BaseModel):
    model_config = ConfigDict(extra="allow")

    shot_id: str
    start_time: float
    end_time: float
    final_duration: float
    characters: list[str] = Field(default_factory=list)
    opening_state: str = ""
    action_path: str = ""
    performance: str = ""
    dialogue: list[DialogueLine] = Field(default_factory=list)
    sound: list[str] = Field(default_factory=list)
    ending_state: str = ""
    first_frame_prompt: str = ""
    video_prompt: str = ""
    negative_constraints: list[str] = Field(default_factory=list)
    generation_segments: list[GenerationSegment] = Field(default_factory=list)


class CharacterOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    character_id: str
    fixed_appearance: str = ""
    initial_state: str = ""
    fixed_costume: str = ""
    fixed_props: list[str] = Field(default_factory=list)
    full_text: str = ""


class DirectorOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    project: dict[str, Any] = Field(default_factory=dict)
    characters: list[CharacterOutput] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    props: list[dict[str, Any]] = Field(default_factory=list)
    shots: list[OutputShot]


Severity = Literal["error", "warning", "info"]


class Issue(BaseModel):
    rule_id: str
    severity: Severity
    title: str
    message: str
    path: str = ""
    evidence: str = ""
    suggestion: str = ""


class VerificationReport(BaseModel):
    passed: bool
    score: int
    errors: int
    warnings: int
    issues: list[Issue]
