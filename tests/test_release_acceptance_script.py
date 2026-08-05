import hashlib
import json
import locale
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest


SCRIPT = Path("scripts/verify_windows_release.ps1")
PS = shutil.which("pwsh") or shutil.which("powershell")
VERSION = "0.3.0"
COMMIT = "93ccc7877e64407950fbb85301ff68b33ee37ee1"


def _write_release(root: Path, *, bad_hash=False, bad_commit=False) -> None:
    setup = root / f"AI-Video-Production-Verifier-Setup-v{VERSION}.exe"
    portable = root / f"AI-Video-Production-Verifier-Portable-v{VERSION}.zip"
    setup.write_bytes(b"setup")
    with zipfile.ZipFile(portable, "w") as archive:
        archive.writestr("AI视频制作核验器.exe", b"exe")
        archive.writestr("_internal/runtime.dll", b"dll")
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (setup, portable)]
    if bad_hash:
        hashes[0] = "0" * 64
    (root / "SHA256SUMS.txt").write_text(f"{hashes[0]} *{setup.name}\n{hashes[1]} *{portable.name}\n", encoding="utf-8")
    (root / f"release_manifest_v{VERSION}.json").write_text(json.dumps({"version": VERSION, "git_commit": "wrong" if bad_commit else COMMIT}), encoding="utf-8")


def _decode_process_output(data: bytes | None) -> str:
    """Decode PowerShell output without assuming its console code page."""
    if data is None:
        return ""
    for encoding in dict.fromkeys(("utf-8-sig", "utf-8", locale.getpreferredencoding(False), "mbcs")):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            pass
    return data.decode("utf-8", errors="replace")


def _run(root: Path, history: Path | None = None, installed: Path | None = None):
    args = [PS, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT.resolve()), "-ReleaseDirectory", str(root), "-ExpectedVersion", VERSION, "-ExpectedCommit", COMMIT]
    if history is not None:
        args += ["-HistoryDirectory", str(history)]
    else:
        args += ["-SkipHistoryCheck"]
    if installed is not None:
        args += ["-InstalledExecutable", str(installed)]
    result = subprocess.run(args, capture_output=True)
    result.stdout = _decode_process_output(result.stdout)
    result.stderr = _decode_process_output(result.stderr)
    return result


def test_script_has_required_safe_static_structure():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '$ErrorActionPreference = "Stop"' in text
    assert "Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8" in text
    assert "Get-Content -LiteralPath $record.FullName -Raw -Encoding UTF8" in text
    assert text.count("RELEASE_ACCEPTANCE_RESULT = OK") == 1


@pytest.mark.skipif(PS is None, reason="PowerShell is required for integration checks")
@pytest.mark.parametrize("bad_hash,bad_commit,expected", [(False, False, 0), (True, False, 1), (False, True, 1)])
def test_release_acceptance_paths(tmp_path, bad_hash, bad_commit, expected):
    _write_release(tmp_path, bad_hash=bad_hash, bad_commit=bad_commit)
    result = _run(tmp_path)
    assert result.returncode == expected
    assert ("RELEASE_ACCEPTANCE_RESULT = OK" in result.stdout) is (expected == 0)


@pytest.mark.skipif(PS is None, reason="PowerShell is required for integration checks")
def test_missing_asset_fails(tmp_path):
    _write_release(tmp_path)
    (tmp_path / f"AI-Video-Production-Verifier-Setup-v{VERSION}.exe").unlink()
    assert _run(tmp_path).returncode != 0


@pytest.mark.skipif(PS is None, reason="PowerShell is required for integration checks")
def test_missing_manifest_fails_without_success_marker(tmp_path):
    _write_release(tmp_path)
    (tmp_path / f"release_manifest_v{VERSION}.json").unlink()
    result = _run(tmp_path)
    assert result.returncode != 0
    assert "Release manifest is missing" in result.stderr
    assert "RELEASE_ACCEPTANCE_RESULT = OK" not in result.stdout + result.stderr


@pytest.mark.skipif(PS is None, reason="PowerShell is required for integration checks")
def test_utf8_history_empty_and_key_cases(tmp_path):
    _write_release(tmp_path)
    history = tmp_path / "中文历史"; history.mkdir()
    empty = _run(tmp_path, history)
    assert empty.returncode == 0 and "History records verified" not in empty.stdout
    valid = {"history_id": "x", "created_at": "2026-01-01T00:00:00Z", "idea": "中文", "result": {"status": "ok"}}
    (history / "有效.json").write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")
    assert _run(tmp_path, history).returncode == 0
    valid["apiKey"] = "sk-abcdefghijklmnop"
    (history / "有效.json").write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")
    assert _run(tmp_path, history).returncode != 0


@pytest.mark.skipif(PS is None, reason="PowerShell is required for integration checks")
def test_installed_plain_file_without_version_information_passes(tmp_path):
    _write_release(tmp_path)
    installed = tmp_path / "installed-test-file.exe"
    installed.write_bytes(b"not a Windows executable")
    result = _run(tmp_path, installed=installed)
    assert result.returncode == 0
    assert "no readable FileVersion or ProductVersion" in result.stdout
