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
        self.directory = directory or root / "AI-Video-Production-Verifier" / "creator_history"
        self.max_records = max_records
        self.directory.mkdir(parents=True, exist_ok=True)

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
        for path in self.directory.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(record, dict) and record.get("history_id") and record.get("created_at"):
                    records.append(record)
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(records, key=lambda item: item["created_at"], reverse=True)

    def load(self, history_id: str) -> dict:
        path = self.directory / f"{history_id}.json"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise KeyError(history_id) from exc
        if not isinstance(record, dict) or record.get("history_id") != history_id:
            raise KeyError(history_id)
        return record

    def delete(self, history_id: str) -> None:
        (self.directory / f"{history_id}.json").unlink(missing_ok=True)

    def clear(self) -> None:
        for path in self.directory.glob("*.json"):
            path.unlink(missing_ok=True)

    def _trim(self) -> None:
        for record in self.list_records()[self.max_records:]:
            self.delete(record["history_id"])
