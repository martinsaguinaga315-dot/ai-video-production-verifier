from datetime import datetime, timezone

from story_generation.generators.creator_generator import (
    CreatorGenerator,
)

from story_generation.models import (
    ArtifactType,
    CreativeBrief,
    FieldProvenance,
    SourceKind,
)


def test_creator_generator_builds_generation_request():
    provenance = FieldProvenance(
        source_kind=SourceKind.USER_EXPLICIT,
        field_path="/idea",
    )

    brief = CreativeBrief(
        brief_id="brief-001",
        idea="047进入地下七层外部接驳舱",
        title="零下七层",
        language="zh-CN",
        target_duration_s=60,
        aspect_ratio="16:9",
        target_platform="AI video",
        target_audience="sci-fi audience",
        visual_style=[
            "中国工业硬科幻",
            "电影质感",
        ],
        provenance=provenance,
    )

    generator = CreatorGenerator()

    result = generator.build_request(
        brief
    )

    assert result.input_artifact_type == ArtifactType.CREATIVE_BRIEF
    assert result.output_artifact_type == ArtifactType.STORYBOARD_DRAFT
    assert result.stage_name == "storyboard_generation"
    assert result.settings.model == "deepseek-chat"
    assert result.created_at.tzinfo is not None
