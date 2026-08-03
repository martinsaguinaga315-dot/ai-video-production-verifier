"""Manually smoke-test the real AI Creator pipeline; not a pytest test."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from story_generation.factories.creator_pipeline_factory import build_creator_pipeline


def main() -> int:
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        print("Creator pipeline smoke test failed: DEEPSEEK_API_KEY is not configured.", file=sys.stderr)
        return 1

    try:
        pipeline = build_creator_pipeline()
        result = pipeline.create(
            idea="047进入地下七层外部接驳舱",
            style="中国工业硬科幻电影",
            goal="生成60秒、镜头时间连续的AI视频分镜",
        )
        output_path = PROJECT_ROOT / "work" / "smoke_creator_pipeline_result.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(
            f"Creator pipeline smoke test failed ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return 1

    storyboard = result.artifact
    issue_codes = [item.code.value for item in result.issues]
    print(f"status: {result.status.value}")
    print(f"storyboard_id: {storyboard.storyboard_id}")
    print(f"shot_count: {len(storyboard.shots)}")
    print(f"target_duration_s: {storyboard.target_duration_s}")
    print(f"issues: {len(result.issues)} ({', '.join(issue_codes) or 'none'})")
    print(f"result_file: {output_path}")
    return 0 if result.status.value == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
