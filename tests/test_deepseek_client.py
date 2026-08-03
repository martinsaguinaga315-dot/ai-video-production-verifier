from story_generation.clients.deepseek_client import DeepSeekClient


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
