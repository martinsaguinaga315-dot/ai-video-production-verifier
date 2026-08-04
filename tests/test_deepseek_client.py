from story_generation.clients.deepseek_client import DeepSeekClient
import pytest


def test_available_reflects_api_key_presence(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert not DeepSeekClient().available()
    assert DeepSeekClient(api_key="test-key").available()


def test_generate_json_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = DeepSeekClient()

    try:
        client.generate_json("system", "user")
    except RuntimeError as exc:
        assert str(exc) == "DeepSeek API key is missing"
    else:
        raise AssertionError("generate_json() should require an API key")


@pytest.mark.parametrize("content", [
    '{"shots": []}',
    '```json\n{"shots": []}\n```',
    '模型结果如下：\n{"message": "brace { inside string}"}\n请查收。',
])
def test_parse_json_object_recovers_supported_response_forms(content):
    assert DeepSeekClient._parse_json_object(content) in ({"shots": []}, {"message": "brace { inside string}"})


@pytest.mark.parametrize("content, message", [
    ('{"shots": [', "truncated JSON response"),
    ('[1, 2, 3]', "must be an object"),
    ('not json at all', "invalid JSON"),
    ('{"a": 1} and {"b": 2}', "multiple conflicting JSON objects"),
])
def test_parse_json_object_rejects_unsupported_response_forms(content, message):
    with pytest.raises(RuntimeError, match=message):
        DeepSeekClient._parse_json_object(content)
