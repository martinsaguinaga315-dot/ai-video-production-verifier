"""Runway Image-to-Video export."""
from __future__ import annotations

from story_generation.models.prompt_pack import PromptPackShot

from .base import PromptPlatformAdapter
from .models import PlatformPromptShot, PromptTargetPlatform


class RunwayPromptAdapter(PromptPlatformAdapter):
    platform = PromptTargetPlatform.RUNWAY

    def adapt_shot(self, shot: PromptPackShot) -> PlatformPromptShot:
        return PlatformPromptShot(
            platform=self.platform, shot_id=shot.shot_id,
            first_frame_prompt=shot.first_frame_prompt, end_frame_prompt=shot.end_frame_prompt,
            video_prompt=shot.video_prompt, negative_prompt="", continuity_notes=shot.continuity_notes,
            usage_notes=("Runway Image-to-Video：输入图像负责主体、构图、灯光和风格；"
                         "文本主要描述主体运动、镜头运动、场景运动、时序、方向和速度。"
                         "使用正向、运动导向的表达；不建议将 Negative 粘贴进视频 Prompt。"
                         "Continuity 仅用于人工制作检查。"),
        )
