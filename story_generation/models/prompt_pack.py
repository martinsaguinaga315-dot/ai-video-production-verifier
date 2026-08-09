"""Strict, portable prompt-pack contracts generated from a storyboard."""
from __future__ import annotations

from pydantic import Field

from .common import StrictModel


class PromptPackShot(StrictModel):
    shot_id: str
    scene_id: str
    sequence: int
    first_frame_prompt: str
    end_frame_prompt: str
    video_prompt: str
    negative_prompt: str
    continuity_notes: str
    generation_target: str = "generic"


class PromptPack(StrictModel):
    prompt_pack_id: str
    storyboard_id: str
    storyboard_version: int
    generation_target: str
    output_language: str = "zh-CN"
    provider: str = "local"
    model: str | None = None
    shots: list[PromptPackShot] = Field(default_factory=list)
    version: int = 1
