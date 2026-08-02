from __future__ import annotations

import llm_audit
from models import DirectorOutput, ProjectFacts
from verification_service import load_json


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def _clean_models() -> tuple[ProjectFacts, DirectorOutput]:
    root = ROOT / "examples" / "clean"
    return (
        ProjectFacts.model_validate(load_json(root / "facts.json")),
        DirectorOutput.model_validate(load_json(root / "director_output.json")),
    )


def test_semantic_client_uses_default_timeout_and_no_retries(monkeypatch) -> None:
    captured = {}
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("DEEPSEEK_SEMANTIC_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("DEEPSEEK_SEMANTIC_MAX_RETRIES", raising=False)
    monkeypatch.setattr(llm_audit, "OpenAI", lambda **kwargs: captured.update(kwargs) or (_ for _ in ()).throw(ConnectionError()))

    facts, output = _clean_models()
    try:
        llm_audit.semantic_audit(facts, output)
    except ConnectionError:
        pass

    assert captured["timeout"] == 60
    assert captured["max_retries"] == 0


def test_semantic_client_configuration_is_bounded(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_SEMANTIC_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("DEEPSEEK_SEMANTIC_MAX_RETRIES", "2")
    assert llm_audit._semantic_timeout_seconds() == 120
    assert llm_audit._semantic_max_retries() == 2

    monkeypatch.setenv("DEEPSEEK_SEMANTIC_TIMEOUT_SECONDS", "0")
    monkeypatch.setenv("DEEPSEEK_SEMANTIC_MAX_RETRIES", "3")
    assert llm_audit._semantic_timeout_seconds() == 60
    assert llm_audit._semantic_max_retries() == 0

    monkeypatch.setenv("DEEPSEEK_SEMANTIC_TIMEOUT_SECONDS", "not-a-number")
    monkeypatch.setenv("DEEPSEEK_SEMANTIC_MAX_RETRIES", "-1")
    assert llm_audit._semantic_timeout_seconds() == 60
    assert llm_audit._semantic_max_retries() == 0
