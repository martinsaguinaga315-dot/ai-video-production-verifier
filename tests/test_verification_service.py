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
    report = run_verification(
        CLEAN / "facts.json",
        CLEAN / "director_output.json",
        semantic=True,
        api_key="secret",
    )
    notice = next(issue for issue in report.issues if issue.rule_id == "SEMANTIC_AUDIT_NOT_EXECUTED")
    assert "API Key无效" in notice.message


@pytest.mark.parametrize(
    ("error_type", "expected_code", "expected_reason"),
    [
        (ConnectionError, "connection_failed", "无法连接DeepSeek"),
        (TimeoutError, "timeout", "DeepSeek语义审计超时"),
    ],
)
def test_recoverable_semantic_failures_preserve_local_report(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    expected_code: str,
    expected_reason: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        verification_service,
        "semantic_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(error_type("secret-api-key")),
    )
    report = run_verification(
        CLEAN / "facts.json", CLEAN / "director_output.json", semantic=True, api_key="secret-api-key"
    )
    notice = next(issue for issue in report.issues if issue.rule_id == "SEMANTIC_AUDIT_NOT_EXECUTED")
    assert notice.severity == "warning"
    assert expected_reason in notice.message
    assert "本地硬规则结果仍有效" in notice.message
    assert "secret-api-key" not in notice.message
    assert notice.evidence == expected_code
    output = tmp_path / "report.json"
    verification_service.write_report(report, output)
    assert "SEMANTIC_AUDIT_NOT_EXECUTED" in output.read_text(encoding="utf-8")


def test_authentication_failure_preserves_local_report_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AuthenticationError(Exception):
        pass

    monkeypatch.setattr(
        verification_service,
        "semantic_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(AuthenticationError("secret-api-key")),
    )
    report = run_verification(
        CLEAN / "facts.json", CLEAN / "director_output.json", semantic=True, api_key="secret-api-key"
    )
    notice = next(issue for issue in report.issues if issue.rule_id == "SEMANTIC_AUDIT_NOT_EXECUTED")
    assert "API Key无效" in notice.message
    assert "secret-api-key" not in notice.message


def test_semantic_failure_keeps_hard_rule_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        verification_service,
        "semantic_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError()),
    )
    report = run_verification(
        ERROR_CASE / "facts.json", ERROR_CASE / "director_output.json", semantic=True, api_key="test-key"
    )
    assert report.passed is False
    assert any(issue.rule_id == "UNKNOWN_CHARACTER" for issue in report.issues)
    assert any(issue.rule_id == "SEMANTIC_AUDIT_NOT_EXECUTED" for issue in report.issues)
