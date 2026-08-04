from pathlib import Path

from app_version import VERSION


def test_v030_release_metadata_and_workflows_are_dynamic():
    assert VERSION == "0.3.0"
    assert '#define MyAppVersion "0.3.0"' in Path("packaging/installer.iss").read_text(encoding="utf-8")
    release = Path(".github/workflows/release-windows.yml").read_text(encoding="utf-8")
    build = Path(".github/workflows/windows-build.yml").read_text(encoding="utf-8")
    assert "v0.2.0" not in release + build
    assert "github.ref_name" in release and "does not match app version" in release
    assert "env.VERSION" in release and "env.VERSION" in build
