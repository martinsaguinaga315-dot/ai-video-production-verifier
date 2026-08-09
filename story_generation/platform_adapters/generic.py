"""Canonical generic prompt export."""
from __future__ import annotations

from story_generation.models.prompt_pack import PromptPackShot

from .base import PromptPlatformAdapter
from .models import PlatformPromptShot, PromptTargetPlatform


class GenericPromptAdapter(PromptPlatformAdapter):
    platform = PromptTargetPlatform.GENERIC

    def adapt_shot(self, shot: PromptPackShot) -> PlatformPromptShot:
        return PlatformPromptShot(
            platform=self.platform, shot_id=shot.shot_id,
            first_frame_prompt=shot.first_frame_prompt, end_frame_prompt=shot.end_frame_prompt,
            video_prompt=shot.video_prompt, negative_prompt=shot.negative_prompt,
            continuity_notes=shot.continuity_notes,
            usage_notes="这是通用 Production Prompt。可继续人工编辑，或作为其他平台适配的源。",
        )
