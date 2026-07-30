from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

from build_support.release_utils import scan_tree, scan_zip, sha256, write_manifest, write_sha256s


def _ico_image_dimensions(payload: bytes) -> tuple[int, int]:
    """Return the dimensions encoded in an ICO PNG or DIB image payload."""
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = struct.unpack_from(">II", payload, 16)
        return width, height

    header_size, width, doubled_height = struct.unpack_from("<Iii", payload)
    assert header_size >= 40
    assert width > 0
    assert doubled_height % 2 == 0
    return width, abs(doubled_height) // 2


def _ico_entries(data: bytes) -> list[tuple[int, int, int, int, int, int, int]]:
    reserved, image_type, image_count = struct.unpack_from("<HHH", data)
    assert reserved == 0
    assert image_type == 1
    assert image_count >= 7
    assert len(data) >= 6 + image_count * 16

    entries = []
    for index in range(image_count):
        directory_width, directory_height, _colors, _reserved, _planes, bits_per_pixel, size, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + index * 16
        )
        assert size > 0
        assert offset >= 6 + image_count * 16
        assert offset + size <= len(data)
        width = 256 if directory_width == 0 else directory_width
        height = 256 if directory_height == 0 else directory_height
        payload_width, payload_height = _ico_image_dimensions(data[offset : offset + size])
        assert (width, height) == (payload_width, payload_height)
        entries.append((directory_width, directory_height, width, height, bits_per_pixel, size, offset))
    return entries


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


def test_packaging_scripts_copy_children_without_literal_wildcards() -> None:
    portable = Path("packaging/package_portable.ps1").read_text(encoding="utf-8")
    windows = Path("packaging/build_windows.ps1").read_text(encoding="utf-8")
    assert "Copy-Item -LiteralPath (Join-Path $source '*')" not in portable
    assert 'Copy-Item -LiteralPath (Join-Path $distDir "$appName\\*")' not in windows
    assert "Get-ChildItem -LiteralPath $source -Force" in portable
    assert "Get-ChildItem -LiteralPath $installerSource -Force" in windows
    assert "Copy-Item -LiteralPath $_.FullName" in portable
    assert "Copy-Item -LiteralPath $_.FullName" in windows


def test_windows_application_icon_is_a_valid_multiresolution_ico() -> None:
    entries = _ico_entries(Path("assets/app.ico").read_bytes())
    actual_sizes = {(width, height) for _raw_width, _raw_height, width, height, _bpp, _size, _offset in entries}
    assert {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)} <= actual_sizes
    assert all(bits_per_pixel == 32 for _raw_width, _raw_height, _width, _height, bits_per_pixel, _size, _offset in entries)
    assert any(
        raw_width == raw_height == 0 and width == height == 256
        for raw_width, raw_height, width, height, _bpp, _size, _offset in entries
    )
