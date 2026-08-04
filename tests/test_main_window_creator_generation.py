import queue
from types import SimpleNamespace

from creator_desktop.main_window import MainWindow
from story_generation.models import GenerationResult, GenerationStatus


class Host:
    def __init__(self):
        self.visible = False

    def grid(self, *args, **kwargs):
        self.visible = True

    def grid_remove(self):
        self.visible = False


class Value:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class View:
    def __init__(self):
        self.busy = []
        self.errors = []
        self.configured = []

    def clear_error(self):
        self.errors.clear()

    def set_api_configured(self, configured):
        self.configured.append(configured)

    def set_busy(self, busy, message=None):
        self.busy.append((busy, message))

    def show_error(self, message):
        self.errors.append(message)


class ResultFrame:
    def __init__(self):
        self.cleared = 0
        self.results = []

    def clear(self):
        self.cleared += 1

    def show_result(self, result):
        self.results.append(result)


class Controller:
    def __init__(self, started=True):
        self.started = started
        self.calls = []

    def start(self, **kwargs):
        self.calls.append(kwargs)
        return self.started


def switch_window():
    return SimpleNamespace(
        creator_generation_host=Host(), creator_host=Host(), professional_host=Host(),
    )


def generation_window(*, controller=None):
    view, result = View(), ResultFrame()
    shown = []
    return SimpleNamespace(
        creator_generation_view=view,
        creator_generation_result_frame=result,
        creator_generation_controller=controller or Controller(),
        _show_creator_generation_input=lambda: shown.append("input"),
        _show_creator_generation_result=lambda: shown.append("result"),
        _open_api_settings=lambda: shown.append("settings"),
        _creator_generation_events=queue.Queue(),
        shown=shown,
    )


def test_top_level_mode_supports_creator_and_preserves_existing_modes():
    window = switch_window()
    MainWindow._switch_mode(window, "AI 创作生成")
    assert window.creator_generation_host.visible is True
    assert window.creator_host.visible is False and window.professional_host.visible is False
    MainWindow._switch_mode(window, "普通创作者模式")
    assert window.creator_host.visible is True
    MainWindow._switch_mode(window, "专业JSON模式")
    assert window.professional_host.visible is True


def test_creator_generation_uses_local_api_key_and_controller(monkeypatch):
    window = generation_window()
    monkeypatch.setattr("creator_desktop.main_window.load_api_key", lambda: "test-key")

    MainWindow._on_creator_generate(window, "创意", "风格", "目标")

    assert window.creator_generation_controller.calls == [{
        "idea": "创意", "style": "风格", "goal": "目标", "api_key": "test-key",
    }]
    assert window.creator_generation_view.configured == [True]
    assert window.creator_generation_result_frame.cleared == 1
    assert not hasattr(window, "api_key")


def test_missing_api_key_does_not_start_controller(monkeypatch):
    window = generation_window()
    monkeypatch.setattr("creator_desktop.main_window.load_api_key", lambda: None)

    MainWindow._on_creator_generate(window, "创意", None, None)

    assert window.creator_generation_controller.calls == []
    assert window.creator_generation_view.configured == [False]
    assert window.creator_generation_view.errors == ["请先在 API 设置中保存 DeepSeek API Key。"]
    assert window.shown == ["settings"]


def test_duplicate_start_does_not_create_another_task(monkeypatch):
    window = generation_window(controller=Controller(started=False))
    monkeypatch.setattr("creator_desktop.main_window.load_api_key", lambda: "test-key")

    MainWindow._on_creator_generate(window, "创意", None, None)

    assert len(window.creator_generation_controller.calls) == 1
    assert window.creator_generation_view.errors == ["已有生成任务正在运行。"]
    assert window.creator_generation_view.busy[-1][0] is True


def test_creator_events_update_view_and_switch_result_without_leaking_error():
    window = generation_window()
    expected = GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft")
    window._creator_generation_events.put({"type": "status", "message": "正在生成 Storyboard"})
    window._creator_generation_events.put({"type": "complete", "result": expected})
    MainWindow._poll_creator_generation_events(window)

    assert window.creator_generation_view.busy == [(True, "正在生成 Storyboard"), (False, "生成完成")]
    assert window.creator_generation_result_frame.results == [expected]
    assert window.shown == ["result"]

    window._creator_generation_events.put({"type": "error", "message": "安全错误"})
    MainWindow._poll_creator_generation_events(window)
    assert window.creator_generation_view.busy[-1] == (False, "生成失败")
    assert window.creator_generation_view.errors == ["安全错误"]
    assert "traceback" not in window.creator_generation_view.errors[-1].lower()
    assert "key" not in window.creator_generation_view.errors[-1].lower()
