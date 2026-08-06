from pathlib import Path

from app_version import VERSION


def test_v032_release_metadata_and_workflows_are_dynamic():
    assert VERSION == "0.3.2"
    installer = Path("packaging/installer.iss").read_text(encoding="utf-8")
    build_script = Path("packaging/build_windows.ps1").read_text(encoding="utf-8")
    portable_script = Path("packaging/package_portable.ps1").read_text(encoding="utf-8")
    assert "#error MyAppVersion must be supplied" in installer
    assert '"/DMyAppVersion=$version"' in build_script
    assert "AI-Video-Production-Verifier-Setup-v$version.exe" in build_script
    assert "AI-Video-Production-Verifier-Portable-v$version.zip" in build_script
    assert "release_manifest_v{args.version}.json" in Path("build_support/generate_release_metadata.py").read_text(encoding="utf-8")
    assert "AI-Video-Production-Verifier-Portable-v$Version" in portable_script
    release = Path(".github/workflows/release-windows.yml").read_text(encoding="utf-8")
    build = Path(".github/workflows/windows-build.yml").read_text(encoding="utf-8")
    assert "v0.2.0" not in release + build
    assert "github.ref_name" in release and "does not match app version" in release
    assert "env.VERSION" in release and "env.VERSION" in build


def test_v032_release_notes_list_dynamic_assets_and_no_history_format_change():
    notes = Path("docs/RELEASE_v0.3.2.md").read_text(encoding="utf-8")
    assert "v0.3.2" in notes
    for asset in (
        "AI-Video-Production-Verifier-Setup-v0.3.2.exe",
        "AI-Video-Production-Verifier-Portable-v0.3.2.zip",
        "SHA256SUMS.txt",
        "release_manifest_v0.3.2.json",
    ):
        assert asset in notes
    assert "Creator history JSON format is unchanged" in notes


def test_v032_changelog_and_v031_history_release_notes_are_present():
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v0.3.2" in changelog and "2026-08-06" in changelog
    assert Path("docs/RELEASE_v0.3.1.md").is_file()
