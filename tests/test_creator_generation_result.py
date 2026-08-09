import tkinter as tk

import customtkinter as ctk
import pytest

from creator_desktop.creator_generation_result import CreatorGenerationResultFrame
from creator_desktop.creator_prompt_pack_store import CreatorPromptPackStore
from story_generation.clients.deepseek_client import DeepSeekApiError
from story_generation.services.ai_prompt_pack_service import AiPromptPackValidationError
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


def test_prompt_pack_selection_and_generation(frame):
    artifact = storyboard([
        {"sequence": 1, "duration_s": 30, "camera": "medium", "action": "move", "performance": "focused", "first_frame_prompt": "opening one", "video_prompt": "motion one"},
        {"sequence": 2, "duration_s": 30, "camera": "wide", "action": "stop", "performance": "calm", "first_frame_prompt": "opening two", "video_prompt": "motion two"},
    ])
    frame.show_result(generation_result(artifact=artifact))
    assert frame.selected_shot_ids() == []
    frame.select_all_shots()
    assert frame.selected_shot_ids() == ["shot-001", "shot-002"]
    frame.clear_shot_selection()
    assert frame.selected_shot_ids() == []
    frame.regenerate_shot_prompt_pack("shot-002")
    assert [shot.shot_id for shot in frame._prompt_pack.shots] == ["shot-002"]
    assert "尾帧提示词：" in frame.rendered_text


def test_prompt_pack_copy_buttons_keep_each_shot_value(frame):
    artifact = storyboard([
        {"sequence": 1, "duration_s": 30, "camera": "medium", "action": "move", "performance": "focused", "first_frame_prompt": "first seed one", "video_prompt": "motion one"},
        {"sequence": 2, "duration_s": 30, "camera": "wide", "action": "stop", "performance": "calm", "first_frame_prompt": "first seed two", "video_prompt": "motion two"},
    ])
    frame.show_result(generation_result(artifact=artifact))
    frame.generate_all_prompt_pack()
    copied = []
    frame._copy = copied.append
    cards = frame.prompt_pack_section.winfo_children()[2:]
    first_actions = cards[0].winfo_children()[1]
    second_actions = cards[1].winfo_children()[1]
    first_actions.winfo_children()[-1].invoke()
    second_actions.winfo_children()[-1].invoke()
    assert "first seed one" in copied[0]
    assert "first seed two" in copied[1]
    assert copied[0] != copied[1]


def test_platform_target_is_separate_from_deepseek_model_and_does_not_mutate_prompt_pack(frame):
    frame.show_result(generation_result())
    frame.generate_all_prompt_pack()
    canonical_before = frame._prompt_pack.model_dump()

    frame.deepseek_model.set("V4 Pro")
    frame.target_platform.set("Runway")
    exported_text = frame._platform_prompt_shot_text(frame._prompt_pack.shots[0])

    assert frame.deepseek_model.get() == "V4 Pro"
    assert frame.target_platform.get() == "Runway"
    assert "目标平台：runway" in exported_text
    assert "不建议用于该平台的视频 Prompt。" in exported_text
    assert frame._prompt_pack.model_dump() == canonical_before


def test_platform_copy_uses_the_current_target_platform(frame):
    frame.show_result(generation_result())
    frame.generate_all_prompt_pack()
    prompt_shot = frame._prompt_pack.shots[0]

    frame.target_platform.set("可灵")
    kling_text = frame._platform_prompt_shot_text(prompt_shot)
    frame.target_platform.set("Veo")
    veo_text = frame._platform_prompt_shot_text(prompt_shot)

    assert "目标平台：kling" in kling_text
    assert prompt_shot.video_prompt in kling_text
    assert "目标平台：veo" in veo_text
    assert prompt_shot.video_prompt in veo_text


def test_prompt_pack_uses_adaptive_per_field_frames_with_visible_copy_actions(frame):
    long_text = "long prompt content " * 400
    artifact = storyboard([{"sequence": 1, "duration_s": 60, "camera": long_text, "action": long_text, "performance": long_text, "first_frame_prompt": long_text, "video_prompt": long_text}])
    frame.show_result(generation_result(artifact=artifact))
    frame.generate_all_prompt_pack()
    card = frame.prompt_pack_section.winfo_children()[2]
    children = card.winfo_children()
    field_frames, actions = children[1:6], children[6]
    assert len(field_frames) == 5
    assert all(field.grid_propagate() for field in field_frames)
    assert all(field.winfo_children()[-1].cget("text") == "复制" for field in field_frames)
    assert actions.winfo_children()[0].cget("text") == "复制本镜头全部提示词"
    assert [field.grid_info()["row"] for field in field_frames] == [1, 2, 3, 4, 5]
    assert actions.grid_info()["row"] == 6
    assert card.grid_propagate()


def test_long_prompt_pack_card_requests_more_height_than_short_card(frame, root):
    short = storyboard([{"sequence": 1, "duration_s": 60, "camera": "medium", "action": "move", "performance": "calm", "first_frame_prompt": "short", "video_prompt": "short"}])
    frame.show_result(generation_result(artifact=short)); frame.generate_all_prompt_pack(); root.update_idletasks()
    short_height = frame.prompt_pack_section.winfo_children()[2].winfo_reqheight()
    long_text = "long prompt content " * 500
    long = storyboard([{"sequence": 1, "duration_s": 60, "camera": long_text, "action": long_text, "performance": long_text, "first_frame_prompt": long_text, "video_prompt": long_text}])
    frame.show_result(generation_result(artifact=long)); frame.generate_all_prompt_pack(); root.update_idletasks()
    long_height = frame.prompt_pack_section.winfo_children()[2].winfo_reqheight()
    assert long_height > short_height


def test_generated_prompt_pack_is_saved_and_restored_in_a_new_result_frame(root, tmp_path):
    store = CreatorPromptPackStore(tmp_path)
    artifact = storyboard()
    first = CreatorGenerationResultFrame(root, prompt_pack_store=store); first.pack()
    first.show_result(generation_result(artifact=artifact)); first.generate_all_prompt_pack()
    original = first._prompt_pack
    assert store.load(artifact.storyboard_id) == original
    first.destroy()
    restored = CreatorGenerationResultFrame(root, prompt_pack_store=store); restored.pack()
    restored.show_result(generation_result(artifact=artifact))
    assert restored._prompt_pack == original
    assert restored.prompt_language.get() == "中文"
    assert "首帧提示词：" in restored.rendered_text
    restored.destroy()


def test_corrupt_saved_pack_does_not_block_storyboard_result(root, tmp_path):
    store = CreatorPromptPackStore(tmp_path)
    artifact = storyboard()
    (tmp_path / f"{artifact.storyboard_id}.json").write_text("{bad", encoding="utf-8")
    result_frame = CreatorGenerationResultFrame(root, prompt_pack_store=store); result_frame.pack()
    result_frame.show_result(generation_result(artifact=artifact))
    assert result_frame._prompt_pack is None
    assert artifact.storyboard_id in result_frame.rendered_text
    result_frame.destroy()


def test_ai_prompt_failure_keeps_the_existing_prompt_pack(frame):
    frame.show_result(generation_result())
    frame.generate_all_prompt_pack()
    original = frame._prompt_pack

    frame._finish_ai_generation(None, "DeepSeek 输出达到长度限制，未生成完整内容。")

    assert frame._prompt_pack is original
    assert "已保留原提示词。" in frame.copy_status.get()


def test_schema_failure_keeps_the_saved_prompt_pack(root, tmp_path):
    store = CreatorPromptPackStore(tmp_path)
    result_frame = CreatorGenerationResultFrame(root, prompt_pack_store=store); result_frame.pack()
    artifact = storyboard()
    result_frame.show_result(generation_result(artifact=artifact))
    result_frame.generate_all_prompt_pack()
    original = result_frame._prompt_pack

    result_frame._finish_ai_generation(None, CreatorGenerationResultFrame._deepseek_error_text(AiPromptPackValidationError("bad schema")))

    assert result_frame._prompt_pack is original
    assert store.load(artifact.storyboard_id) == original
    result_frame.destroy()


@pytest.mark.parametrize(("code", "expected"), [
    ("length_empty", "DeepSeek 输出达到长度限制，未生成完整内容。"),
    ("empty_content", "DeepSeek 返回空内容，请重试。"),
])
def test_deepseek_empty_response_errors_are_user_friendly(code, expected):
    error = DeepSeekApiError("internal detail", error_code=code)

    assert CreatorGenerationResultFrame._deepseek_error_text(error) == expected


def test_schema_validation_error_is_not_presented_as_an_api_failure():
    assert CreatorGenerationResultFrame._deepseek_error_text(AiPromptPackValidationError("bad schema")) == "DeepSeek 返回的提示词格式不完整。"


def test_other_local_errors_are_not_presented_as_an_api_failure():
    assert CreatorGenerationResultFrame._deepseek_error_text(RuntimeError("bad local state")) == "提示词处理失败。"


def test_api_errors_remain_presented_as_api_failures():
    assert CreatorGenerationResultFrame._deepseek_error_text(DeepSeekApiError("safe api error")) == "DeepSeek API 请求失败。"
