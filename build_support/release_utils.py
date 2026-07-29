"""Dependency-free helpers for Windows distribution scripts."""
from __future__ import annotations
import hashlib, json, re, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from app_version import VERSION

SENSITIVE_PATTERNS = {"DEEPSEEK_API_KEY": re.compile(r"DEEPSEEK_API_KEY\s*=\s*\S+", re.I), "OPENAI_API_KEY": re.compile(r"OPENAI_API_KEY\s*=\s*\S+", re.I), "API-key-like token": re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")}
FORBIDDEN_PATH_PARTS = {".git", "__pycache__", ".pytest_cache", ".env", "my_project"}

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()

def scan_tree(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if {part.lower() for part in relative.parts} & FORBIDDEN_PATH_PARTS:
            findings.append(f"forbidden path: {relative}"); continue
        if not path.is_file() or path.suffix.lower() in {".exe", ".dll", ".pyd", ".ico", ".png"}: continue
        content = path.read_bytes().decode("utf-8", errors="ignore")
        findings.extend(f"{label}: {relative}" for label, pattern in SENSITIVE_PATTERNS.items() if pattern.search(content))
    return findings

def scan_zip(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return [f"forbidden archive path: {name}" for name in archive.namelist() if {part.lower() for part in Path(name).parts} & FORBIDDEN_PATH_PARTS]

def write_sha256s(paths: Iterable[Path], destination: Path) -> None:
    destination.write_text("".join(f"{sha256(path)} *{path.name}\n" for path in paths if path.is_file()), encoding="utf-8")

def write_manifest(destination: Path, *, commit: str, python_version: str, pyinstaller_version: str, test_result: str, artifacts: Iterable[Path], smoke_passed: bool, scan_passed: bool, installer_built: bool, portable_built: bool) -> None:
    payload = {"version": VERSION, "git_commit": commit, "build_time_utc": datetime.now(timezone.utc).isoformat(), "python_version": python_version, "pyinstaller_version": pyinstaller_version, "test_result": test_result, "artifacts": [{"name": p.name, "size": p.stat().st_size, "sha256": sha256(p)} for p in artifacts if p.is_file()], "sensitive_scan_passed": scan_passed, "exe_smoke_passed": smoke_passed, "installer_built": installer_built, "portable_built": portable_built}
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
