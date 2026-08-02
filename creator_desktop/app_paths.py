from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DATA_FOLDER = "AIVideoProductionVerifier"


def application_root() -> Path:
    """Return the bundled resource root without relying on the CWD."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    return application_root().joinpath(*parts)


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = root / APP_DATA_FOLDER
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def temp_dir() -> Path:
    root = Path(os.environ.get("TEMP", Path(os.environ.get("TMP", app_data_dir() / "temp"))))
    path = root / APP_DATA_FOLDER
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_smoke_test() -> bool:
    return os.environ.get("AIVPV_SMOKE_TEST") == "1"
