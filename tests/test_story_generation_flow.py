from story_generation.generators.creator_generator import CreatorGenerator
from story_generation.services.story_service import StoryService


class MockDeepSeekClient:
    def __init__(self):
        self.calls = []

    def generate_json(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return {"storyboard_id": "storyboard-001", "shots": []}


def test_create_story_calls_client_and_returns_ai_json():
    client = MockDeepSeekClient()
    service = StoryService(generator=CreatorGenerator(), client=client)

    result = service.create_story(
        idea="047进入地下七层外部接驳舱",
        style="中国工业硬科幻",
        goal="生成AI视频分镜",
    )

    assert result == {"storyboard_id": "storyboard-001", "shots": []}
    assert len(client.calls) == 1
    system_prompt, user_prompt = client.calls[0]
    assert "JSON object" in system_prompt
    assert '"shots"' in system_prompt
    assert "非空数组" in system_prompt
    assert "严格等于 60 秒" in system_prompt
    assert "禁止 Markdown" in system_prompt
    assert "禁止 ```json" in system_prompt
    assert "storyboard_generation" in user_prompt
    assert "047进入地下七层外部接驳舱" in user_prompt
