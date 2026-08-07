import tkinter as tk

import customtkinter as ctk
import pytest

from creator_desktop.creator_generation_result import CreatorGenerationResultFrame
from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.models import (
    GenerationIssue,
    GenerationIssueCode,
    GenerationMetadata,
    GenerationResult,
    GenerationStatus,
)


@pytest.fixture(scope="module")
def root():
    try:
        app = ctk.CTk()
    except tk.TclError:
        pytest.skip("CustomTkinter requires an available display")
    app.withdraw()
    yield app
    app.destroy()


@pytest.fixture
def frame(root):
    result_frame = CreatorGenerationResultFrame(root)
    result_frame.pack(fill="both", expand=True)
    root.update_idletasks()
    yield result_frame
    result_frame.destroy()


def storyboard(shots=None):
    return StoryboardBuilder().build({
        "target_duration_s": 60,
        "shots": shots if shots is not None else [{
            "sequence": 1, "duration_s": 60, "camera": "全景", "action": "舱门开启",
            "performance": "克制", "first_frame_prompt": "首帧", "video_prompt": "视频", "sound": ["机械声"],
        }],
    })


def generation_result(*, status=GenerationStatus.SUCCEEDED, artifact=None, issues=None, metadata=None):
    return GenerationResult(
        status=status,
        artifact_type="storyboard_draft",
        artifact=storyboard() if artifact is None else artifact,
        issues=issues or [],
        metadata=metadata,
    )


def visible_text(widget):
    return widget.rendered_text


def test_succeeded_result_shows_storyboard_summary_and_no_issues(frame):
    artifact = storyboard()
    frame.show_result(generation_result(artifact=artifact))
    text = visible_text(frame)
    assert artifact.storyboard_id in text
    assert "镜头数量：1" in text
    assert "目标时长：60.0" in text
    assert "未发现制片硬规则问题。" in text


def test_repair_metadata_is_displayed(frame):
    metadata = GenerationMetadata(
        request_id="repair-request", stage_name="storyboard_generation", model="test", prompt_version="v1",
        status=GenerationStatus.SUCCEEDED, repair_count=1, parent_request_id="first-request",
    )
    frame.show_result(generation_result(metadata=metadata))
    text = visible_text(frame)
    assert "AI 修正：已执行一次" in text
    assert "first-request" in text


def test_failed_result_shows_issue_details(frame):
    issue = GenerationIssue(
        code=GenerationIssueCode.DURATION_MISMATCH, severity="error", path="shots",
        message="总时长不匹配", suggestion="重新分配时长", related_ids=["shot-001"],
    )
    frame.show_result(generation_result(status=GenerationStatus.FAILED, issues=[issue]))
    text = visible_text(frame)
    assert "DURATION_MISMATCH" in text
    assert "总时长不匹配" in text
    assert "路径：shots" in text


def test_multiple_shots_show_core_fields_and_prompts(frame):
    artifact = storyboard([
        {"sequence": 1, "duration_s": 30, "camera": "近景", "action": "人物进入", "performance": "紧张", "first_frame_prompt": "首帧一", "video_prompt": "视频一"},
        {"sequence": 2, "duration_s": 30, "camera": "远景", "action": "舱门关闭", "performance": "平静", "first_frame_prompt": "首帧二", "video_prompt": "视频二"},
    ])
    frame.show_result(generation_result(artifact=artifact))
    text = visible_text(frame)
    for expected in ("Sequence：1", "Sequence：2", "近景", "舱门关闭", "首帧一", "视频二"):
        assert expected in text


def test_none_artifact_is_safe(frame):
    result = GenerationResult(status=GenerationStatus.FAILED, artifact_type="storyboard_draft", artifact=None)
    frame.show_result(result)
    assert "未提供可展示的 Storyboard artifact。" in visible_text(frame)


def test_clear_restores_waiting_message(frame):
    frame.show_result(generation_result())
    frame.clear()
    assert visible_text(frame).count("等待 Storyboard 生成结果。") == 1


def test_none_metadata_and_empty_shots_are_safe(frame):
    frame.show_result(generation_result(artifact=storyboard([]), metadata=None))
    text = visible_text(frame)
    assert "AI 修正：未触发" in text
    assert "未生成镜头。" in text


def test_display_never_contains_api_key(frame):
    frame.show_result(generation_result())
    assert "api_key" not in visible_text(frame).lower()


def test_long_shot_text_uses_an_adaptive_card_with_separate_actions(frame):
    long_text = "长文本提示词 " * 200
    artifact = storyboard([{
        "sequence": 1, "duration_s": 60, "camera": long_text, "action": long_text,
        "performance": long_text, "first_frame_prompt": long_text, "video_prompt": long_text,
    }])
    frame.show_result(generation_result(artifact=artifact))
    card = frame.shot_cards[0]
    assert card.body.grid_info()["row"] == 1
    assert card.actions.grid_info()["row"] == 2
    assert len(card.actions.winfo_children()) == 3


def test_result_root_uses_transparent_background(root):
    result_frame = CreatorGenerationResultFrame(root)
    assert result_frame.cget("fg_color") == "transparent"
    result_frame.destroy()
