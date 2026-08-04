"""Manually inspect each production Creator pipeline stage; not a pytest test."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from story_generation.factories.creator_pipeline_factory import build_creator_pipeline


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find_shot_paths(value: Any, path: str = "$") -> list[tuple[str, int | None]]:
    found: list[tuple[str, int | None]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            if key == "shots":
                found.append((item_path, len(item) if isinstance(item, list) else None))
            found.extend(_find_shot_paths(item, item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_find_shot_paths(item, f"{path}[{index}]"))
    return found


def main() -> int:
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        print("Creator response debug failed: DEEPSEEK_API_KEY is not configured.", file=sys.stderr)
        return 1

    output_dir = PROJECT_ROOT / "work"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        pipeline = build_creator_pipeline()
        story_service = pipeline.story_service
        generation_request = story_service.create_story_request(
            idea="047进入地下七层外部接驳舱",
            style="中国工业硬科幻电影",
            goal="生成60秒、镜头时间连续的AI视频分镜",
        )
        _write_json(output_dir / "debug_generation_request.json", generation_request.model_dump(mode="json"))

        raw_response = story_service.create_story(
            idea="047进入地下七层外部接驳舱",
            style="中国工业硬科幻电影",
            goal="生成60秒、镜头时间连续的AI视频分镜",
        )
        _write_json(output_dir / "debug_deepseek_raw_response.json", raw_response)

        storyboard = pipeline.storyboard_builder.build(raw_response)
        _write_json(output_dir / "debug_storyboard_draft.json", storyboard.model_dump(mode="json"))

        result = pipeline.validation_service.validate(storyboard)
        _write_json(output_dir / "debug_generation_result.json", result.model_dump(mode="json"))
    except Exception as exc:
        print(f"Creator response debug failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1

    shot_paths = _find_shot_paths(raw_response)
    raw_shot_count = sum(count for _, count in shot_paths if count is not None)
    print(f"deepseek_top_level_fields: {', '.join(sorted(raw_response)) or 'none'}")
    print(f"has_shots: {'yes' if shot_paths else 'no'}")
    print(f"shots_paths: {', '.join(path for path, _ in shot_paths) or 'none'}")
    print(f"raw_shot_count: {raw_shot_count}")
    print(f"builder_shot_count: {len(storyboard.shots)}")
    print(f"issue_codes: {', '.join(item.code.value for item in result.issues) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
