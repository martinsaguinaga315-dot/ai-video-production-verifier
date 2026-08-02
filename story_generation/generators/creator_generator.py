from __future__ import annotations

from datetime import datetime, timezone

from story_generation.models import (
    ArtifactType,
    CreativeBrief,
    GenerationRequest,
    GenerationSettings,
)

class CreatorGenerator:
    """
    AI Creator 第一阶段生成器。

    当前职责：
    - 接收 CreativeBrief
    - 构造 Storyboard 生成请求
    - 输出 GenerationRequest

    不负责：
    - DeepSeek 调用
    - JSON解析
    - Storyboard生成
    """

    def __init__(
        self,
        model: str = "deepseek-chat",
    ):
        self.model = model

    def build_request(
        self,
        brief: CreativeBrief,
    ) -> GenerationRequest:
       
        return GenerationRequest(
            request_id=f"storyboard-{brief.brief_id}",
            stage_name="storyboard_generation",
            input_artifact_type=ArtifactType.CREATIVE_BRIEF,
            output_artifact_type=ArtifactType.STORYBOARD_DRAFT,
            settings=GenerationSettings(
                quality_mode="standard",
                model=self.model,
                max_tokens=4096,
                timeout_s=45,
                max_retries=2,
            ),
            created_at=datetime.now(timezone.utc),
        )
