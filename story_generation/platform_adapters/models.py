"""Temporary, platform-specific prompt export contracts."""
from __future__ import annotations

from enum import StrEnum

from story_generation.models.common import StrictModel


class PromptTargetPlatform(StrEnum):
    GENERIC = "generic"
    KLING = "kling"
    JIMENG = "jimeng"
    RUNWAY = "runway"
    VEO = "veo"


class PlatformPromptShot(StrictModel):
    """A non-persistent view of one canonical :class:`PromptPackShot`."""

    platform: PromptTargetPlatform
    shot_id: str
    first_frame_prompt: str
    end_frame_prompt: str
    video_prompt: str
    negative_prompt: str
    continuity_notes: str
    usage_notes: str
