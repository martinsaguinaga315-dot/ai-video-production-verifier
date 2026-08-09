"""Local, atomic persistence for the latest prompt pack per storyboard."""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from story_generation.models import PromptPack


class CreatorPromptPackStore:
    def __init__(self, directory: Path | None = None) -> None:
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self.directory = directory or root / "AIVideoProductionVerifier" / "creator_prompt_packs"

    def save(self, prompt_pack: PromptPack) -> Path:
        if not isinstance(prompt_pack, PromptPack):
            raise TypeError("CreatorPromptPackStore only persists canonical PromptPack instances")
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.directory / f"{prompt_pack.storyboard_id}.json"
        temporary = self.directory / f".{prompt_pack.storyboard_id}.tmp"
        temporary.write_text(json.dumps(prompt_pack.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
        return destination

    def load(self, storyboard_id: str) -> PromptPack | None:
        try:
            payload = json.loads((self.directory / f"{storyboard_id}.json").read_text(encoding="utf-8"))
            prompt_pack = PromptPack.model_validate(payload)
            return prompt_pack if prompt_pack.storyboard_id == storyboard_id else None
        except (OSError, json.JSONDecodeError, ValidationError):
            return None

    def exists(self, storyboard_id: str) -> bool:
        return self.load(storyboard_id) is not None
