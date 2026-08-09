"""Veo-oriented high-information-density export."""
from __future__ import annotations

from story_generation.models.prompt_pack import PromptPackShot

from .base import PromptPlatformAdapter
from .models import PlatformPromptShot, PromptTargetPlatform


class VeoPromptAdapter(PromptPlatformAdapter):
    platform = PromptTargetPlatform.VEO

    def adapt_shot(self, shot: PromptPackShot) -> PlatformPromptShot:
        return PlatformPromptShot(
            platform=self.platform, shot_id=shot.shot_id,
            first_frame_prompt=shot.first_frame_prompt, end_frame_prompt=shot.end_frame_prompt,
            video_prompt=shot.video_prompt, negative_prompt=shot.negative_prompt,
            continuity_notes=shot.continuity_notes,
            usage_notes=("首帧提示词：首帧图像参考；尾帧提示词：尾帧图像参考；"
                         "视频提示词：视频描述；Negative：排除项；"
                         "Continuity：人工连续性检查。"),
        )
