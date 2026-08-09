import pytest

from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.services.ai_prompt_pack_service import AiPromptPackService, AiPromptPackValidationError


class FakeClient:
    model = "deepseek-chat"
    def __init__(self, response): self.response, self.calls = response, []
    def generate_json(self, system, user, **kwargs): self.calls.append((system, user, kwargs)); return self.response


def storyboard():
    return StoryboardBuilder().build({"storyboard_id": "board", "target_duration_s": 12, "shots": [
        {"sequence": 1, "duration_s": 6, "camera": "static", "action": "start", "performance": "calm", "first_frame_prompt": "one", "video_prompt": "one"},
        {"sequence": 2, "duration_s": 6, "camera": "track", "action": "finish", "performance": "focused", "first_frame_prompt": "two", "video_prompt": "two"},
    ]})


def response(shot_id="shot-001"):
    return {"shot_id": shot_id, "first_frame_prompt": "first", "end_frame_prompt": "end", "video_prompt": "video", "negative_prompt": "negative", "continuity_notes": "continuity"}


def test_ai_service_generates_valid_deepseek_pack_with_context():
    client = FakeClient(response())
    pack = AiPromptPackService(client).generate(storyboard(), shot_ids=["shot-001"], output_language="en")
    assert pack.provider == "deepseek" and pack.model == "deepseek-chat" and pack.output_language == "en"
    assert len(client.calls) == 1 and "next_shot" in client.calls[0][1]
    assert client.calls[0][2] == {"thinking": False, "max_tokens": 8192}


def test_ai_service_fills_only_a_missing_shot_id():
    payload = response()
    payload.pop("shot_id")

    pack = AiPromptPackService(FakeClient(payload)).generate(storyboard(), shot_ids=["shot-001"])

    assert pack.shots[0].shot_id == "shot-001"


def test_ai_service_discards_harmless_unknown_response_fields():
    pack = AiPromptPackService(FakeClient({**response(), "note": "ignored"})).generate(storyboard(), shot_ids=["shot-001"])

    assert not hasattr(pack.shots[0], "note")


@pytest.mark.parametrize("bad", [response("unknown"), {**response(), "first_frame_prompt": ""}, {"current_shot": {}}])
def test_ai_service_rejects_invalid_response(bad):
    with pytest.raises(AiPromptPackValidationError):
        AiPromptPackService(FakeClient(bad)).generate(storyboard(), shot_ids=["shot-001"])


def test_ai_service_failure_does_not_produce_a_replacement_pack():
    client = FakeClient(response())
    client.generate_json = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("DeepSeek failed"))

    with pytest.raises(RuntimeError, match="DeepSeek failed"):
        AiPromptPackService(client).generate(storyboard(), shot_ids=["shot-001"])


def test_ai_service_malformed_json_failure_does_not_produce_a_replacement_pack():
    client = FakeClient(response())
    client.generate_json = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("DeepSeek returned invalid JSON"))

    with pytest.raises(RuntimeError, match="invalid JSON"):
        AiPromptPackService(client).generate(storyboard(), shot_ids=["shot-001"])
