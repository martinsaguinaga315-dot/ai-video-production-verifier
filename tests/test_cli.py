from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import verify


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "examples" / "clean"
ERROR_CASE = ROOT / "examples" / "unknown_character_error"


def _run(*args: str, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "verify.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env=env,
    )


def test_cli_clean_exit_code_zero() -> None:
    result = _run(str(CLEAN / "facts.json"), str(CLEAN / "director_output.json"))
    assert result.returncode == 0
    assert '"passed": true' in result.stdout
    assert '"score": 100' in result.stdout


def test_cli_error_exit_code_one() -> None:
    result = _run(str(ERROR_CASE / "facts.json"), str(ERROR_CASE / "director_output.json"))
    assert result.returncode == 1
    assert "UNKNOWN_CHARACTER" in result.stdout


def test_cli_output_option_writes_report(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    result = _run(
        str(CLEAN / "facts.json"),
        str(CLEAN / "director_output.json"),
        "--output",
        str(output),
    )
    assert result.returncode == 0
    assert output.exists()
    assert '"score": 100' in output.read_text(encoding="utf-8")


def test_cli_error_remains_utf8_when_child_starts_as_cp1252() -> None:
    result = _run(
        str(ERROR_CASE / "facts.json"),
        str(ERROR_CASE / "director_output.json"),
        env_overrides={"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
    )
    assert result.returncode == 1
    assert "UNKNOWN_CHARACTER" in result.stdout
    assert "UnicodeEncodeError" not in result.stderr


def test_cli_clean_remains_utf8_when_child_starts_as_cp1252() -> None:
    result = _run(
        str(CLEAN / "facts.json"),
        str(CLEAN / "director_output.json"),
        env_overrides={"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
    )
    assert result.returncode == 0
    assert '"passed": true' in result.stdout
    assert '"score": 100' in result.stdout
    assert "UnicodeEncodeError" not in result.stderr


def test_cli_schema_error_writes_to_stderr_as_utf8(tmp_path: Path) -> None:
    invalid_facts = tmp_path / "invalid_facts.json"
    invalid_facts.write_text('{"title": "missing fields"}', encoding="utf-8")
    result = _run(
        str(invalid_facts),
        str(CLEAN / "director_output.json"),
        env_overrides={"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
    )
    assert result.returncode == 2
    assert result.stderr
    assert any(ord(character) > 127 for character in result.stderr)
    assert "UnicodeEncodeError" not in result.stderr


def test_configure_utf8_stdio_allows_streams_without_reconfigure(monkeypatch) -> None:
    monkeypatch.setattr(verify.sys, "stdout", object())
    monkeypatch.setattr(verify.sys, "stderr", object())
    verify.configure_utf8_stdio()
