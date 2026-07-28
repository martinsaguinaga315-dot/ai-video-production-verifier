from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "examples" / "clean"
ERROR_CASE = ROOT / "examples" / "unknown_character_error"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "verify.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_cli_clean_exit_code_zero() -> None:
    result = _run(str(CLEAN / "facts.json"), str(CLEAN / "director_output.json"))
    assert result.returncode == 0
    assert '"passed": true' in result.stdout


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
