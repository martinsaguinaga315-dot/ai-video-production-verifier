from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from story_generation.models import GenerationResult


class CreatorHistoryStore:
    def __init__(self, directory: Path | None = None, max_records: int = 50) -> None:
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self.directory = directory or root / "AIVideoProductionVerifier" / "creator_history"
        self._legacy_directory = root / "AI-Video-Production-Verifier" / "creator_history" if directory is None else None
        self.max_records = max_records
        self.directory.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy()

    def save(self, *, idea: str, style: str | None, goal: str | None, result: GenerationResult) -> str:
        history_id = str(uuid4())
        payload = {"history_id": history_id, "created_at": datetime.now(timezone.utc).isoformat(), "idea": idea, "style": style, "goal": goal, "result": result.model_dump(mode="json")}
        temporary = self.directory / f".{history_id}.tmp"
        destination = self.directory / f"{history_id}.json"
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
        self._trim()
        return history_id

    def list_records(self) -> list[dict]:
        records = []
        seen = set()
        for folder in (self.directory, self._legacy_directory):
            if folder is None:
                continue
            for path in folder.glob("*.json"):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(record, dict) and record.get("history_id") and record.get("created_at") and record["history_id"] not in seen:
                        records.append(record); seen.add(record["history_id"])
                except (OSError, json.JSONDecodeError):
                    continue
        return sorted(records, key=lambda item: item["created_at"], reverse=True)

    def load(self, history_id: str) -> dict:
        for folder in (self.directory, self._legacy_directory):
            if folder is None: continue
            try:
                record = json.loads((folder / f"{history_id}.json").read_text(encoding="utf-8"))
                if isinstance(record, dict) and record.get("history_id") == history_id: return record
            except (OSError, json.JSONDecodeError): continue
        raise KeyError(history_id)

    def delete(self, history_id: str) -> None:
        (self.directory / f"{history_id}.json").unlink(missing_ok=True)

    def clear(self) -> None:
        for folder in (self.directory, self._legacy_directory):
            if folder is None: continue
            for path in folder.glob("*.json"):
                path.unlink(missing_ok=True)

    def _trim(self) -> None:
        for record in self.list_records()[self.max_records:]:
            self.delete(record["history_id"])

    def _migrate_legacy(self) -> None:
        if self._legacy_directory is None or not self._legacy_directory.is_dir():
            return
        for record in self.list_records():
            destination = self.directory / f"{record['history_id']}.json"
            if destination.exists():
                continue
            try:
                temporary = self.directory / f".{record['history_id']}.tmp"
                temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                temporary.replace(destination)
            except OSError:
                continue
