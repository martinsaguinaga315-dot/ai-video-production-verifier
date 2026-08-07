import queue
from types import SimpleNamespace

from creator_desktop.main_window import MainWindow, _recent_project_title
from story_generation.models import GenerationResult, GenerationStatus
from story_generation.builders.storyboard_builder import StoryboardBuilder
from creator_desktop.creator_history_store import CreatorHistoryStore


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


class Button:
    def __init__(self): self.states = []
    def configure(self, **kwargs): self.states.append(kwargs)


class Logger:
    def __init__(self): self.messages = []
    def info(self, message, *args): self.messages.append((message, args))
    def exception(self, message, *args): self.messages.append((message, args))


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
        creator_generation_view=SimpleNamespace(generate_button=SimpleNamespace(cget=lambda _name: "normal")),
        _show_creator_generation_input=lambda: None,
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


def test_switching_to_ai_restores_creator_input_from_a_subview():
    window = switch_window()
    calls = []
    window._show_creator_generation_input = lambda: calls.append("input")
    MainWindow._switch_mode(window, "AI 创作模式")
    assert window.creator_generation_host.visible is True
    assert calls == ["input"]


def test_history_result_is_restored_and_shown_without_returning_to_input():
    artifact = StoryboardBuilder().build({"target_duration_s": 30, "shots": [{"duration_s": 30}]})
    stored = GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft", artifact=artifact).model_dump(mode="json")
    shown, input_calls = [], []
    window = SimpleNamespace(
        _log=Logger(),
        creator_generation_last_button=Button(),
        creator_generation_result_frame=SimpleNamespace(show_result=shown.append),
        _show_creator_generation_result=lambda: shown.append("result-page"),
        _show_creator_generation_input=lambda: input_calls.append("input"),
    )
    MainWindow._show_history_result(window, {"result": stored})
    assert shown[0].artifact.target_duration_s == 30
    assert shown[-1] == "result-page"
    assert input_calls == []


def test_saved_history_round_trip_restores_storyboard_and_shows_result(tmp_path):
    artifact = StoryboardBuilder().build({"target_duration_s": 30, "shots": [{"duration_s": 30}]})
    saved_result = GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft", artifact=artifact)
    store = CreatorHistoryStore(tmp_path)
    store.save(idea="创意", style=None, goal=None, result=saved_result)
    shown = []
    window = SimpleNamespace(
        _log=Logger(),
        creator_generation_last_button=Button(),
        creator_generation_result_frame=SimpleNamespace(show_result=shown.append),
        _show_creator_generation_result=lambda: shown.append("result-page"),
    )
    MainWindow._show_history_result(window, store.list_records()[0])
    assert shown[0].artifact.target_duration_s == 30
    assert shown[-1] == "result-page"


def test_corrupt_history_result_shows_a_clear_error(monkeypatch):
    messages = []
    window = SimpleNamespace(_log=Logger())
    monkeypatch.setattr("creator_desktop.main_window.messagebox.showerror", lambda *args, **kwargs: messages.append(args[1]))
    MainWindow._show_history_result(window, {"result": {"not": "a result"}})
    assert messages == ["无法读取该历史结果，记录可能来自旧版本或数据已损坏。"]


def test_history_result_does_not_depend_on_a_missing_last_result_button():
    artifact = StoryboardBuilder().build({"target_duration_s": 30, "shots": [{"duration_s": 30}]})
    shown = []
    window = SimpleNamespace(
        _log=Logger(),
        creator_generation_result_frame=SimpleNamespace(show_result=shown.append),
        _show_creator_generation_result=lambda: shown.append("result-page"),
    )
    MainWindow._show_history_result(window, {"history_id": "history-a", "result": GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft", artifact=artifact).model_dump(mode="json")})
    assert shown[-1] == "result-page"
    assert any(message == "history_result_render_completed history_id=%s" for message, _args in window._log.messages)


def test_result_subview_shows_the_ai_host_and_hides_other_creator_subviews():
    window = SimpleNamespace(
        _log=Logger(),
        creator_generation_host=Host(),
        creator_generation_view=Host(),
        creator_history_view=Host(),
        creator_generation_result_host=Host(),
    )
    MainWindow._show_creator_generation_result(window)
    assert window.creator_generation_host.visible is True
    assert window.creator_generation_view.visible is False
    assert window.creator_history_view.visible is False
    assert window.creator_generation_result_host.visible is True


def test_recent_project_title_is_safely_truncated():
    assert _recent_project_title({"idea": "城市办公穿越海边的长篇创意故事以及后续内容"}, maximum=16) == "城市办公穿越海边的长篇创意故事以…"


def test_recent_project_title_normalizes_whitespace_and_uses_default_limit():
    assert _recent_project_title({"idea": "  城市   办公  穿越 海边 的 长篇 创意  "}) == "城市 办公 穿越 海边 的 长篇…"


def test_creator_generation_uses_local_api_key_and_controller(monkeypatch):
    window = generation_window()
    monkeypatch.setattr("creator_desktop.main_window.load_api_key", lambda: "test-key")

    MainWindow._on_creator_generate(window, "创意", "风格", "目标")

    assert window.creator_generation_controller.calls == [{
        "idea": "创意", "style": "风格", "goal": "目标", "target_duration_s": 60, "aspect_ratio": "16:9", "api_key": "test-key",
    }]


def test_creator_generation_forwards_selected_duration_and_ratio(monkeypatch):
    window = generation_window()
    monkeypatch.setattr("creator_desktop.main_window.load_api_key", lambda: "test-key")
    MainWindow._on_creator_generate(window, "创意", None, None, 30, "9:16")
    assert window.creator_generation_controller.calls[0]["target_duration_s"] == 30
    assert window.creator_generation_controller.calls[0]["aspect_ratio"] == "9:16"
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
