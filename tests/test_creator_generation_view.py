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
    app.withdraw()
    yield app
    app.destroy()


@pytest.fixture
def view(root):
    calls = []
    frame = CreatorGenerationView(root, lambda idea, style, goal: calls.append((idea, style, goal)))
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
    assert calls == [("雨夜接驳舱", "工业科幻", "生成分镜")]


def test_empty_optional_inputs_are_none(view):
    frame, calls = view
    fill(frame, idea="创意", style="", goal="")
    frame.generate_button.invoke()
    assert calls == [("创意", None, None)]


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
