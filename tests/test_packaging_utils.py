from __future__ import annotations

import json
import zipfile
from pathlib import Path

from build_support.release_utils import scan_tree, scan_zip, sha256, write_manifest, write_sha256s


def test_sha256_and_manifest_include_artifact_metadata(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"; artifact.write_bytes(b"release")
    checksums, manifest = tmp_path / "SHA256SUMS.txt", tmp_path / "manifest.json"
    write_sha256s([artifact], checksums)
    write_manifest(manifest, commit="abc", python_version="3.11", pyinstaller_version="6.12", test_result="75 passed", artifacts=[artifact], smoke_passed=True, scan_passed=True, installer_built=False, portable_built=True)
    assert sha256(artifact) in checksums.read_text(encoding="utf-8")
    assert json.loads(manifest.read_text(encoding="utf-8"))["artifacts"][0]["name"] == "artifact.bin"


def test_sensitive_scan_passes_for_clean_tree_and_fails_for_mock_key(tmp_path: Path) -> None:
    (tmp_path / "README.txt").write_text("safe release", encoding="utf-8")
    assert scan_tree(tmp_path) == []
    (tmp_path / "config.txt").write_text("DEEPSEEK_API_KEY=mock-secret-value", encoding="utf-8")
    assert scan_tree(tmp_path)


def test_sensitive_scan_rejects_forbidden_build_paths_and_archives(tmp_path: Path) -> None:
    cache = tmp_path / "__pycache__"; cache.mkdir(); (cache / "x.pyc").write_bytes(b"x")
    assert scan_tree(tmp_path)
    archive = tmp_path / "portable.zip"
    with zipfile.ZipFile(archive, "w") as output: output.writestr("app/.git/config", "x")
    assert scan_zip(archive)


def test_windows_build_reads_unicode_app_name_as_utf8() -> None:
    script = Path("packaging/build_windows.ps1").read_text(encoding="utf-8")
    assert "$env:PYTHONIOENCODING = 'utf-8'" in script
    assert "$env:PYTHONUTF8 = '1'" in script
    assert "Application name metadata was empty." in script


def test_frozen_build_verifies_pyinstaller_internal_resources() -> None:
    script = Path("packaging/verify_build.ps1").read_text(encoding="utf-8")
    assert '"$AppName\\_internal\\$required"' in script


def test_frozen_build_smoke_test_waits_for_clean_exit() -> None:
    script = Path("packaging/verify_build.ps1").read_text(encoding="utf-8")
    assert "$process.WaitForExit(10000)" in script
    assert "$process.ExitCode -ne 0" in script
    assert "Frozen EXE smoke test timed out after 10 seconds." in script
    assert "Frozen EXE exited early" not in script
