from __future__ import annotations

from pathlib import Path

import app_version
from creator_desktop import app_paths


def test_version_metadata_is_single_source_of_truth() -> None:
    assert app_version.APP_NAME == "AI视频制作核验器"
    assert app_version.APP_NAME_EN == "AI Video Production Verifier"
    assert app_version.VERSION == "0.2.0"
    assert app_version.PUBLISHER == "Muzifan AIGC"


def test_source_resources_are_relative_to_application_not_cwd(monkeypatch) -> None:
    monkeypatch.setattr(app_paths.sys, "frozen", False, raising=False)
    assert app_paths.resource_path("examples").name == "examples"
    assert app_paths.resource_path("examples").is_dir()


def test_frozen_resources_use_pyinstaller_resource_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_paths.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert app_paths.resource_path("assets", "app.ico") == tmp_path / "assets" / "app.ico"


def test_user_data_and_logs_never_use_install_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    data, logs = app_paths.app_data_dir(), app_paths.log_dir()
    assert data == tmp_path / "LocalAppData" / "AIVideoProductionVerifier"
    assert logs == data / "logs"
    assert logs.is_dir()


def test_smoke_mode_is_explicit_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("AIVPV_SMOKE_TEST", raising=False)
    assert app_paths.is_smoke_test() is False
    monkeypatch.setenv("AIVPV_SMOKE_TEST", "1")
    assert app_paths.is_smoke_test() is True
