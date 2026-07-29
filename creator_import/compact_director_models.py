"""Small, response-stable models used only before DirectorOutput construction."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from models import DialogueLine


class RequiredEventSupport(BaseModel):
    required_event: str
    supported: bool = False
    source_quote: str = ""


class CompactProjectDraft(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str = ""


class CompactCharacterDraft(BaseModel):
    model_config = ConfigDict(extra="allow")
    character_id: str
    fixed_appearance: str = ""
    # Evidence is kept only while converting the compact draft.  It never
    # becomes part of DirectorOutput or a verification report.
    appearance_source_quote: str = ""
    initial_state: str = ""
    fixed_costume: str = ""
    fixed_props: list[str] = Field(default_factory=list)
    full_text: str = ""


class CompactShotDraft(BaseModel):
    model_config = ConfigDict(extra="allow")
    shot_id: str
    characters: list[str] = Field(default_factory=list)
    opening_state: str = ""
    action_path: str = ""
    performance: str = ""
    dialogue: list[DialogueLine] = Field(default_factory=list)
    sound: list[str] = Field(default_factory=list)
    ending_state: str = ""
    negative_constraints: list[str] = Field(default_factory=list)
    required_event_support: list[RequiredEventSupport] = Field(default_factory=list)


class CompactDirectorDraft(BaseModel):
    model_config = ConfigDict(extra="allow")
    project: CompactProjectDraft = Field(default_factory=CompactProjectDraft)
    characters: list[CompactCharacterDraft] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    props: list[dict[str, Any]] = Field(default_factory=list)
    shots: list[CompactShotDraft]
