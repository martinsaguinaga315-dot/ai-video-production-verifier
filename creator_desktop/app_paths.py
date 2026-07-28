from __future__ import annotations

import os
from pathlib import Path


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = root / "AIVideoProductionVerifier"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
