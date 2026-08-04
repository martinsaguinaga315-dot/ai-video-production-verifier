from __future__ import annotations


from story_generation.models import CreativeBrief, FieldProvenance, SourceKind
from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.prompts.storyboard_prompts import (
    STORYBOARD_GENERATION_SYSTEM_PROMPT,
    build_storyboard_prompt,
)


class StoryService:
    """
    AI Creator 创意生成服务层。

    负责协调：

    用户创意
        ↓
    CreatorGenerator
        ↓
    AI Client
        ↓
    Storyboard结果


    当前版本:
    v0.3.0 skeleton
    """

    def __init__(
        self,
        generator,
        client=None,
    ):
        self.generator = generator
        self.client = client


    def _build_brief(
        self,
        idea: str,
        style: str | None = None,
        goal: str | None = None,
    ) -> CreativeBrief:
        return CreativeBrief(
            brief_id="brief-user-idea",
            idea=idea,
            title=idea,
            language="zh-CN",
            target_duration_s=60,
            aspect_ratio="16:9",
            target_platform="AI video",
            target_audience="general",
            visual_style=[style] if style else [],
            must_include=[goal] if goal else [],
            provenance=FieldProvenance(
                source_kind=SourceKind.USER_EXPLICIT,
                field_path="/idea",
            ),
        )

    def create_story_request(
        self,
        idea: str,
        style: str | None = None,
        goal: str | None = None,
    ):
        brief = self._build_brief(idea, style, goal)
        return self.generator.build_request(brief)

    def create_story(
        self,
        idea: str,
        style: str | None = None,
        goal: str | None = None,
    ) -> dict:
        if self.client is None:
            raise RuntimeError("DeepSeek client is required to create a story")

        brief = self._build_brief(idea, style, goal)
        request = self.generator.build_request(brief)
        user_prompt = build_storyboard_prompt(
            idea=brief.idea,
            style=", ".join(brief.visual_style) or None,
            goal=", ".join(brief.must_include) or None,
        )
        user_prompt += f"\nGeneration request: {request.request_id}\nStage: {request.stage_name}\n"
        return self.client.generate_json(STORYBOARD_GENERATION_SYSTEM_PROMPT, user_prompt)

    def create_storyboard(
        self,
        idea: str,
        style: str | None = None,
        goal: str | None = None,
    ):
        payload = self.create_story(idea, style, goal)
        return StoryboardBuilder().build(payload)
