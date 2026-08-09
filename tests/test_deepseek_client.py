from types import SimpleNamespace
from unittest.mock import Mock

from story_generation.clients.deepseek_client import DeepSeekApiError, DeepSeekClient
import pytest


def _response(content, finish_reason="stop", reasoning_content=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, reasoning_content=reasoning_content),
        finish_reason=finish_reason,
    )])


def _client_with_create(monkeypatch, *responses):
    create = Mock(side_effect=responses)
    monkeypatch.setattr(
        "story_generation.clients.deepseek_client.OpenAI",
        lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    return DeepSeekClient(api_key="test-api-key"), create


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


@pytest.mark.parametrize(("thinking", "expected"), [
    (False, {"thinking": {"type": "disabled"}}),
    (True, {"thinking": {"type": "enabled"}}),
])
def test_generate_json_passes_explicit_thinking_configuration(monkeypatch, thinking, expected):
    client, create = _client_with_create(monkeypatch, _response('{"ok": true}'))

    assert client.generate_json("system", "user", thinking=thinking) == {"ok": True}
    assert create.call_args.kwargs["extra_body"] == expected


def test_generate_json_omits_thinking_configuration_when_unspecified(monkeypatch):
    client, create = _client_with_create(monkeypatch, _response('{"ok": true}'))

    client.generate_json("system", "user")

    assert "extra_body" not in create.call_args.kwargs


def test_generate_json_passes_max_tokens_and_json_mode(monkeypatch):
    client, create = _client_with_create(monkeypatch, _response('{"ok": true}'))

    client.generate_json("system", "user", max_tokens=8192)

    assert create.call_args.kwargs["max_tokens"] == 8192
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}


def test_generate_json_reports_length_when_content_is_empty(monkeypatch):
    client, create = _client_with_create(monkeypatch, _response(None, "length"), _response(None, "length"))

    with pytest.raises(DeepSeekApiError, match="length limit") as error:
        client.generate_json("system", "user", thinking=False, max_tokens=8192)

    assert error.value.error_code == "length_empty"
    assert create.call_count == 2


def test_generate_json_retries_empty_content_once_with_same_request_options(monkeypatch):
    client, create = _client_with_create(monkeypatch, _response(""), _response('{"ok": true}', reasoning_content="do not keep"))

    assert client.generate_json("system", "user", thinking=False, max_tokens=8192) == {"ok": True}

    assert create.call_count == 2
    for call in create.call_args_list:
        assert call.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
        assert call.kwargs["max_tokens"] == 8192


def test_generate_json_empty_content_and_errors_do_not_leak_api_key(monkeypatch):
    client, _ = _client_with_create(monkeypatch, _response(None), _response(None))

    with pytest.raises(DeepSeekApiError) as error:
        client.generate_json("system", "user")

    assert error.value.error_code == "empty_content"
    assert "test-api-key" not in str(error.value)
    assert "authorization" not in str(error.value).lower()


def test_generate_json_api_errors_do_not_leak_api_key_or_authorization(monkeypatch):
    client, _ = _client_with_create(monkeypatch, Exception("Authorization: Bearer test-api-key"))

    with pytest.raises(DeepSeekApiError) as error:
        client.generate_json("system", "user")

    assert "test-api-key" not in str(error.value)
    assert "authorization" not in str(error.value).lower()


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
