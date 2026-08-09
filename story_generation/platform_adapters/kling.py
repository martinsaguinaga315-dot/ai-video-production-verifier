"""Kling-oriented export while retaining canonical field boundaries."""
from __future__ import annotations

from story_generation.models.prompt_pack import PromptPackShot

from .base import PromptPlatformAdapter
from .models import PlatformPromptShot, PromptTargetPlatform


class KlingPromptAdapter(PromptPlatformAdapter):
    platform = PromptTargetPlatform.KLING

    def adapt_shot(self, shot: PromptPackShot) -> PlatformPromptShot:
        return PlatformPromptShot(
            platform=self.platform, shot_id=shot.shot_id,
            first_frame_prompt=shot.first_frame_prompt, end_frame_prompt=shot.end_frame_prompt,
            video_prompt=shot.video_prompt,
            negative_prompt=shot.negative_prompt, continuity_notes=shot.continuity_notes,
            usage_notes=("推荐工作流：首帧提示词用于首帧图片；尾帧提示词用于首尾帧参考；"
                         "视频提示词用于视频 Prompt；Negative 用作负面/排除参考；"
                         "Continuity 用于人工核对人物、道具、空间和光线连续性。"
                         "请按当前平台可用能力分别填写，不假定固定 UI 字段。"),
        )
