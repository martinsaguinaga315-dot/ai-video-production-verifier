from story_generation.generators.creator_generator import (
    CreatorGenerator,
)


def test_creator_generator_build_request():
    generator = CreatorGenerator()

    result = generator.build_request(
        idea="047进入地下七层外部接驳舱",
        style="中国工业硬科幻电影",
        goal="生成AI视频分镜提示词",
    )

    assert result["type"] == "storyboard_generation"
    assert result["idea"] == "047进入地下七层外部接驳舱"
    assert "Prompt" not in result["type"]
    assert "047" in result["prompt"]
