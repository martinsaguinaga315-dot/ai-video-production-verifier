import queue
import threading

import pytest

import creator_desktop.creator_generation_controller as controller_module
from creator_desktop.creator_generation_controller import CreatorGenerationController
from story_generation.models import GenerationResult, GenerationStatus


class FakePipeline:
    def __init__(self, result=None, error=None, started=None, release=None):
        self.result = result
        self.error = error
        self.started = started
        self.release = release
        self.calls = []

    def create(self, *, idea, style, goal):
        self.calls.append({"idea": idea, "style": style, "goal": goal})
        if self.started:
            self.started.set()
        if self.release:
            self.release.wait(timeout=2)
        if self.error:
            raise self.error
        return self.result


class FakePipelineFactory:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.calls = []

    def __call__(self, *, api_key=None):
        self.calls.append({"api_key": api_key})
        return self.pipeline


def events_until_complete(events):
    received = []
    while not received or received[-1]["type"] not in {"complete", "error"}:
        received.append(events.get(timeout=2))
    return received


def result():
    return GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft")


def test_normal_generation_posts_status_and_original_result():
    events = queue.Queue()
    expected = result()
    pipeline = FakePipeline(result=expected)
    factory = FakePipelineFactory(pipeline)
    controller = CreatorGenerationController(events, factory)

    assert controller.start(idea="雨夜接驳", style="硬科幻", goal="生成分镜") is True
    received = events_until_complete(events)

    assert [event["type"] for event in received] == ["status", "complete"]
    assert received[-1]["result"] is expected
    assert pipeline.calls == [{"idea": "雨夜接驳", "style": "硬科幻", "goal": "生成分镜"}]


def test_parameters_and_api_key_are_routed_only_to_their_expected_targets():
    events = queue.Queue()
    pipeline = FakePipeline(result=result())
    factory = FakePipelineFactory(pipeline)
    controller = CreatorGenerationController(events, factory)

    controller.start(idea="创意", style="风格", goal="目标", api_key="secret-key")
    received = events_until_complete(events)

    assert factory.calls == [{"api_key": "secret-key"}]
    assert pipeline.calls == [{"idea": "创意", "style": "风格", "goal": "目标"}]
    assert all("secret-key" not in str(event.get("message", "")) for event in received)


def test_duplicate_start_does_not_start_a_second_worker():
    events = queue.Queue()
    started, release = threading.Event(), threading.Event()
    pipeline = FakePipeline(result=result(), started=started, release=release)
    controller = CreatorGenerationController(events, FakePipelineFactory(pipeline))

    assert controller.start(idea="创意") is True
    assert started.wait(timeout=2)
    assert controller.start(idea="第二次") is False
    release.set()
    events_until_complete(events)

    assert len(pipeline.calls) == 1


def test_generation_error_is_safe_and_running_state_is_restored():
    events = queue.Queue()
    pipeline = FakePipeline(error=RuntimeError("secret-key provider detail"))
    controller = CreatorGenerationController(events, FakePipelineFactory(pipeline))

    assert controller.start(idea="创意") is True
    received = events_until_complete(events)

    assert received[-1]["type"] == "error"
    assert "secret-key" not in received[-1]["message"]
    assert controller.is_running is False


def test_empty_idea_does_not_start_worker_or_call_pipeline():
    events = queue.Queue()
    pipeline = FakePipeline(result=result())
    factory = FakePipelineFactory(pipeline)
    controller = CreatorGenerationController(events, factory)

    with pytest.raises(ValueError, match="不能为空"):
        controller.start(idea="  ")

    assert factory.calls == []
    assert pipeline.calls == []
    assert controller.is_running is False


def test_worker_thread_is_daemon(monkeypatch):
    events = queue.Queue()
    captured = {}

    class ImmediateThread:
        def __init__(self, *, target, args, daemon, name):
            captured.update(target=target, args=args, daemon=daemon, name=name)

        def start(self):
            captured["target"](*captured["args"])

    monkeypatch.setattr(controller_module.threading, "Thread", ImmediateThread)
    controller = CreatorGenerationController(events, FakePipelineFactory(FakePipeline(result=result())))

    assert controller.start(idea="创意") is True
    assert captured["daemon"] is True
    assert captured["name"] == "creator-generation-worker"
