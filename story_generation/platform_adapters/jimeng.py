"""Jimeng-oriented export."""
from __future__ import annotations

from story_generation.models.prompt_pack import PromptPackShot

from .base import PromptPlatformAdapter
from .models import PlatformPromptShot, PromptTargetPlatform


class JimengPromptAdapter(PromptPlatformAdapter):
    platform = PromptTargetPlatform.JIMENG

    def adapt_shot(self, shot: PromptPackShot) -> PlatformPromptShot:
        return PlatformPromptShot(
            platform=self.platform, shot_id=shot.shot_id,
            first_frame_prompt=shot.first_frame_prompt, end_frame_prompt=shot.end_frame_prompt,
            video_prompt=shot.video_prompt, negative_prompt=shot.negative_prompt,
            continuity_notes=shot.continuity_notes,
            usage_notes=("优先将视频提示词用于视频生成提示。若平台提供独立运镜控制，"
                         "优先使用该参数，避免与文本 Prompt 的运镜描述冲突。"
                         "首尾帧、Negative 和 Continuity 均为独立制作参考。"),
        )
