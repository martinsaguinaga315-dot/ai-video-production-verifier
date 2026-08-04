"""No-network import/UI smoke for Creator modules, suitable for frozen builds."""
from __future__ import annotations
import tempfile
import customtkinter as ctk
from creator_desktop.creator_generation_result import CreatorGenerationResultFrame
from creator_desktop.creator_history_store import CreatorHistoryStore
from story_generation.factories.creator_pipeline_factory import build_creator_pipeline
from story_generation.models import GenerationResult, GenerationStatus

def main() -> int:
    root = ctk.CTk(); root.withdraw()
    try:
        build_creator_pipeline(api_key="smoke-key")
        frame = CreatorGenerationResultFrame(root)
        result = GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft", artifact={"shots": []})
        frame.show_result(result)
        frame._copy_json()
        with tempfile.TemporaryDirectory() as folder:
            CreatorHistoryStore(__import__("pathlib").Path(folder)).save(idea="smoke", style=None, goal=None, result=result)
        root.update_idletasks()
        return 0
    except Exception as exc:
        print(f"Creator UI smoke failed: {type(exc).__name__}")
        return 1
    finally:
        root.destroy()

if __name__ == "__main__":
    raise SystemExit(main())
