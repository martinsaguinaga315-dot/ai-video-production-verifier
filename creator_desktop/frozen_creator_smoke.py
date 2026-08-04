"""No-network Creator smoke entry point bundled into the frozen desktop app."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import customtkinter as ctk

from creator_desktop.creator_generation_result import CreatorGenerationResultFrame
from creator_desktop.creator_generation_view import CreatorGenerationView
from creator_desktop.creator_history_store import CreatorHistoryStore
from story_generation.factories.creator_pipeline_factory import build_creator_pipeline
from story_generation.models import GenerationResult, GenerationStatus


def run_frozen_creator_smoke() -> int:
    """Exercise bundled Creator imports and UI components without a network request."""
    root = None
    try:
        build_creator_pipeline()
        root = ctk.CTk()
        root.withdraw()
        CreatorGenerationView(root, on_generate=lambda _idea, _style, _goal: None)
        frame = CreatorGenerationResultFrame(root)
        result = GenerationResult(
            status=GenerationStatus.SUCCEEDED,
            artifact_type="storyboard_draft",
            artifact={"shots": []},
        )
        frame.show_result(result)
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        with tempfile.TemporaryDirectory() as folder:
            CreatorHistoryStore(Path(folder)).save(idea="smoke", style=None, goal=None, result=result)
        root.update_idletasks()
        return 0
    except Exception as exc:
        print(f"Frozen Creator smoke failed: {type(exc).__name__}")
        return 1
    finally:
        if root is not None:
            root.destroy()
