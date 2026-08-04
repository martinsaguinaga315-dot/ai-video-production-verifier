"""Background controller for AI Creator storyboard generation."""
from __future__ import annotations

import queue
import threading
from typing import Callable

from pydantic import ValidationError

from story_generation.factories.creator_pipeline_factory import build_creator_pipeline


class CreatorGenerationController:
    """Run one Creator pipeline request off the UI thread."""

    def __init__(
        self,
        event_queue: queue.Queue[dict[str, object]],
        pipeline_factory: Callable = build_creator_pipeline,
    ) -> None:
        self._events = event_queue
        self._pipeline_factory = pipeline_factory
        self._lock = threading.Lock()
        self._running = False

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def start(
        self,
        *,
        idea: str,
        style: str | None = None,
        goal: str | None = None,
        api_key: str | None = None,
    ) -> bool:
        if not idea or not idea.strip():
            raise ValueError("创意 idea 不能为空。")
        with self._lock:
            if self._running:
                return False
            self._running = True
        threading.Thread(
            target=self._run,
            args=(idea, style, goal, api_key),
            daemon=True,
            name="creator-generation-worker",
        ).start()
        return True

    def _run(self, idea: str, style: str | None, goal: str | None, api_key: str | None) -> None:
        try:
            self._events.put({
                "type": "status",
                "message": "正在生成 Storyboard，必要时将执行一次 AI 修正。",
            })
            pipeline = self._pipeline_factory(api_key=api_key)
            result = pipeline.create(idea=idea, style=style, goal=goal)
            self._events.put({"type": "complete", "result": result})
        except Exception as exc:
            self._events.put({"type": "error", "message": self._safe_error_message(exc)})
        finally:
            with self._lock:
                self._running = False

    @staticmethod
    def _safe_error_message(error: Exception) -> str:
        if isinstance(error, ValidationError):
            return "生成结果结构无效，请调整创意后重试。"
        if isinstance(error, RuntimeError):
            return "生成 Storyboard 失败，请检查 API 配置或稍后重试。"
        return "生成 Storyboard 时发生意外错误，请稍后重试。"
