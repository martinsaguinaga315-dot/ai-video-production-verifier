from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import verification_service
from creator_desktop.ui_errors import friendly_error
from models import Issue
from verification_service import (
    InputFileNotFoundError,
    InputJsonError,
    InputSchemaError,
    SemanticVerificationError,
    run_verification,
)


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "examples" / "clean"
ERROR_CASE = ROOT / "examples" / "unknown_character_error"


def test_clean_example_passes() -> None:
    report = run_verification(CLEAN / "facts.json", CLEAN / "director_output.json")
    assert report.passed is True
    assert report.score == 100
    assert report.errors == 0


def test_unknown_character_example_reports_expected_issue() -> None:
    report = run_verification(ERROR_CASE / "facts.json", ERROR_CASE / "director_output.json")
    assert report.passed is False
    assert any(issue.rule_id == "UNKNOWN_CHARACTER" for issue in report.issues)


def test_invalid_json_is_mapped(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(InputJsonError):
        run_verification(broken, CLEAN / "director_output.json")


def test_invalid_schema_is_mapped(tmp_path: Path) -> None:
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps({"title": "missing required fields"}), encoding="utf-8")
    with pytest.raises(InputSchemaError):
        run_verification(facts, CLEAN / "director_output.json")


def test_missing_file_is_mapped() -> None:
    with pytest.raises(InputFileNotFoundError):
        run_verification("not-found-facts.json", CLEAN / "director_output.json")


def test_local_mode_never_calls_semantic_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*args, **kwargs):
        raise AssertionError("semantic audit must not run in local mode")

    monkeypatch.setattr(verification_service, "semantic_audit", unexpected)
    report = run_verification(CLEAN / "facts.json", CLEAN / "director_output.json")
    assert report.passed


def test_semantic_mode_uses_mock_and_restores_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    def fake_audit(*args, **kwargs):
        captured["key"] = os.getenv("DEEPSEEK_API_KEY")
        return [
            Issue(
                rule_id="SEMANTIC_STATE_CONTINUITY",
                severity="warning",
                title="mock",
                message="mock warning",
            )
        ]

    monkeypatch.setattr(verification_service, "semantic_audit", fake_audit)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    report = run_verification(
        CLEAN / "facts.json",
        CLEAN / "director_output.json",
        semantic=True,
        api_key="test-key",
    )
    assert captured["key"] == "test-key"
    assert "DEEPSEEK_API_KEY" not in os.environ
    assert report.warnings == 1


def test_api_key_is_not_exposed_by_semantic_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_audit(*args, **kwargs):
        raise RuntimeError("Authorization: Bearer secret-api-key")

    monkeypatch.setattr(verification_service, "semantic_audit", fake_audit)
    with pytest.raises(SemanticVerificationError) as caught:
        run_verification(
            CLEAN / "facts.json",
            CLEAN / "director_output.json",
            semantic=True,
            api_key="secret-api-key",
        )
    assert "secret-api-key" not in str(caught.value)


def test_provider_error_has_a_specific_safe_chinese_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AuthenticationError(Exception):
        pass

    monkeypatch.setattr(
        verification_service,
        "semantic_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(AuthenticationError("secret")),
    )
    with pytest.raises(SemanticVerificationError) as caught:
        run_verification(
            CLEAN / "facts.json",
            CLEAN / "director_output.json",
            semantic=True,
            api_key="secret",
        )
    assert caught.value.code == "api_key_invalid"
    assert friendly_error(caught.value) == "API Key无效。"
