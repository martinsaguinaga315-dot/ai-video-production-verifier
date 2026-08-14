import tkinter as tk

import customtkinter as ctk
import pytest

from creator_desktop.creator_generation_view import CreatorGenerationView


@pytest.fixture(scope="module")
def root():
    try:
        app = ctk.CTk()
    except tk.TclError:
        pytest.skip("CustomTkinter requires an available display")
    app.geometry("900x600")
    app.deiconify()
    app.update_idletasks()
    yield app
    app.destroy()


@pytest.fixture
def view(root):
    calls = []
    frame = CreatorGenerationView(root, lambda idea, style, goal, duration, aspect: calls.append((idea, style, goal, duration, aspect)))
    frame.pack(fill="both", expand=True)
    root.update_idletasks()
    yield frame, calls
    frame.destroy()


def fill(view, *, idea="创意", style="风格", goal="目标"):
    view.idea_textbox.insert("1.0", idea)
    view.style_entry.insert(0, style)
    view.goal_entry.insert(0, goal)


def test_normal_input_is_trimmed_and_sent_to_callback(view):
    frame, calls = view
    fill(frame, idea="  雨夜接驳舱  ", style="  工业科幻  ", goal="  生成分镜  ")
    frame.generate_button.invoke()
    assert calls == [("雨夜接驳舱", "工业科幻", "生成分镜", 60, "16:9")]


def test_empty_optional_inputs_are_none(view):
    frame, calls = view
    fill(frame, idea="创意", style="", goal="")
    frame.generate_button.invoke()
    assert calls == [("创意", None, None, 60, "16:9")]


def test_empty_idea_shows_error_without_callback(view):
    frame, calls = view
    fill(frame, idea="  ")
    frame.generate_button.invoke()
    assert calls == []
    assert "请输入创意" in frame.error_text.get()
    assert frame.run_status.get() == "生成失败"


def test_busy_state_disables_and_restores_inputs(view):
    frame, _ = view
    frame.set_busy(True)
    assert frame.generate_button.cget("state") == "disabled"
    assert frame.idea_textbox._textbox.cget("state") == "disabled"
    assert "正在生成 Storyboard" in frame.run_status.get()
    frame.set_busy(False)
    assert frame.generate_button.cget("state") == "normal"
    assert frame.style_entry.cget("state") == "normal"
    assert frame.run_status.get() == "准备就绪"


def test_api_configuration_status(view):
    frame, _ = view
    frame.set_api_configured(True)
    assert frame.api_status.get() == "API：已配置"
    frame.set_api_configured(False)
    assert frame.api_status.get() == "API：未配置"


def test_callback_exception_is_not_exposed(view):
    frame, _ = view
    frame._on_generate = lambda *_: (_ for _ in ()).throw(RuntimeError("secret-api-key"))
    fill(frame)
    frame.generate_button.invoke()
    assert frame.error_text.get() == "无法启动生成，请稍后重试。"
    assert "secret-api-key" not in frame.error_text.get()


def test_more_requirements_toggles_without_losing_values(view):
    frame, _ = view
    fill(frame, style="电影感", goal="完成分镜")
    assert frame.optional_open is False
    frame.toggle_optional_requirements()
    assert frame.optional_open is True
    frame.toggle_optional_requirements()
    assert frame.optional_open is False
    assert frame.get_inputs()[1:] == ("电影感", "完成分镜")


def test_character_count_and_generate_button_are_independent_controls(view):
    frame, _ = view
    assert frame.character_count_label is not frame.generate_button


def test_dynamic_sections_refresh_the_page_scroll_region(view):
    frame, _ = view
    refreshes = []
    frame.page_scroll.refresh_scroll_region = lambda: refreshes.append(True)

    frame.toggle_optional_requirements()
    frame.toggle_settings()
    frame.update_idletasks()

    assert frame.page_scroll._parent_canvas.winfo_exists()
    assert len(refreshes) == 2


def test_creation_card_keeps_the_designed_content_width(view):
    frame, _ = view
    frame.update_idletasks()

    assert frame.creation_card.cget("width") == 820
    assert frame.idea_textbox.cget("width") == 200
    assert frame.idea_textbox.winfo_width() == 792 * frame._get_widget_scaling()


def test_character_count_is_before_generate_button_in_footer(view):
    frame, _ = view
    frame.update_idletasks()
    assert frame.character_count_label.winfo_x() < frame.generate_button.winfo_x()


def test_character_count_updates_with_idea_input(view):
    frame, _ = view
    frame.idea_textbox.insert("1.0", "四个字符")
    frame._update_character_count()
    assert frame.character_count.get() == "4 字"


def test_production_settings_are_real_and_update_the_summary(view):
    frame, _ = view
    assert frame.target_duration_s.get() == 60
    assert frame.aspect_ratio.get() == "16:9"
    assert frame.settings_summary.get() == "60 秒 · 16:9 · 自动镜头 · 中文输出"
    frame._set_duration(30)
    frame.aspect_ratio.set("9:16")
    assert frame.settings_summary.get() == "30 秒 · 9:16 · 自动镜头 · 中文输出"


def test_generation_includes_production_settings_and_busy_locks_them(view):
    frame, calls = view
    fill(frame)
    frame._set_duration(30)
    frame.aspect_ratio.set("9:16")
    frame.generate_button.invoke()
    assert calls == [("创意", "风格", "目标", 30, "9:16")]
    frame.set_busy(True)
    assert frame.duration_slider.cget("state") == "disabled"
    assert frame.duration_entry.cget("state") == "disabled"
    assert all(button.cget("state") == "disabled" for button in frame.duration_shortcut_buttons)
    assert all(button.cget("state") == "disabled" for button in frame.aspect_selector._buttons_dict.values())
    frame.set_busy(False)
    assert frame.duration_slider.cget("state") == "normal"
    assert frame.duration_entry.cget("state") == "normal"


@pytest.mark.parametrize("duration", [3, 37, 83, 347, 600])
def test_slider_synchronizes_all_duration_views(view, duration):
    frame, _ = view
    frame._on_slider_duration(duration)
    assert frame.target_duration_s.get() == duration
    assert frame.duration_entry.get() == str(duration)
    assert frame.settings_summary.get().startswith(f"{duration} 秒")


@pytest.mark.parametrize("duration", [15, 30, 60, 120, 300, 600])
def test_shortcuts_synchronize_all_duration_views(view, duration):
    frame, _ = view
    frame._set_duration(duration)
    assert frame.target_duration_s.get() == duration
    assert int(frame.duration_slider.get()) == duration
    assert frame.duration_entry.get() == str(duration)


def test_duration_entry_synchronizes_and_clamps_numeric_values(view):
    frame, _ = view
    for entered, expected in (("37", 37), ("1", 3), ("999", 600), ("0", 3), ("601", 600)):
        frame.duration_entry.delete(0, "end")
        frame.duration_entry.insert(0, entered)
        assert frame._commit_duration_entry() is True
        assert frame.target_duration_s.get() == expected
        assert int(frame.duration_slider.get()) == expected
        assert frame.duration_entry.get() == str(expected)


@pytest.mark.parametrize("entered", ["", "abc", "3.5", "-3"])
def test_invalid_duration_entry_blocks_generation(view, entered):
    frame, calls = view
    fill(frame)
    frame.duration_entry.delete(0, "end")
    frame.duration_entry.insert(0, entered)
    frame.generate_button.invoke()
    assert calls == []
    assert frame.error_text.get() == "请输入 3～600 之间的整数秒数。"


def test_arbitrary_duration_is_sent_to_generation_callback(view):
    frame, calls = view
    fill(frame)
    frame._set_duration(347)
    frame.generate_button.invoke()
    assert calls[-1][3] == 347
