from __future__ import annotations


from story_generation.models import CreativeBrief, FieldProvenance, SourceKind


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


    def create_story_request(
        self,
        idea: str,
        style: str | None = None,
        goal: str | None = None,
    ):
        brief = CreativeBrief(
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

        return self.generator.build_request(brief)
