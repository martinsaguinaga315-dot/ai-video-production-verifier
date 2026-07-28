"""Background controller for the staged creator workflow."""
from __future__ import annotations

import queue
import threading
from typing import Callable

from models import DirectorOutput, ProjectFacts, VerificationReport
from verification_service import run_verification_models


class AnalysisController:
    def __init__(
        self,
        *,
        facts_extractor: Callable = None,
        director_parser: Callable = None,
        verifier: Callable[..., VerificationReport] = run_verification_models,
    ) -> None:
        from creator_import.director_parser import parse_director_output_from_text
        from creator_import.facts_extractor import extract_facts_from_text

        self._facts_extractor = facts_extractor or extract_facts_from_text
        self._director_parser = director_parser or parse_director_output_from_text
        self._verifier = verifier
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._lock = threading.Lock()
        self._running = False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def _start(self, target, args: tuple) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
        threading.Thread(target=target, args=args, daemon=True, name="creator-analysis-worker").start()
        return True

    def start_facts(self, script_text: str, client) -> bool:
        return self._start(self._run_facts, (script_text, client))

    def start_director(self, director_text: str, facts: ProjectFacts, client) -> bool:
        return self._start(self._run_director, (director_text, facts, client))

    def start_verification(
        self, facts: ProjectFacts, output: DirectorOutput, *, semantic: bool, api_key: str | None
    ) -> bool:
        return self._start(self._run_verification, (facts, output, semantic, api_key))

    def _finish(self) -> None:
        with self._lock:
            self._running = False

    def _run_facts(self, script_text: str, client) -> None:
        try:
            self.events.put(("status", "正在提取项目事实"))
            facts = self._facts_extractor(script_text, client)
            self.events.put(("facts_ready", facts))
        except Exception as exc:
            self.events.put(("error", exc))
        finally:
            self._finish()

    def _run_director(self, director_text: str, facts: ProjectFacts, client) -> None:
        try:
            self.events.put(("status", "正在解析导演方案"))
            output = self._director_parser(director_text, facts, client)
            self.events.put(("director_ready", output))
        except Exception as exc:
            self.events.put(("error", exc))
        finally:
            self._finish()

    def _run_verification(self, facts, output, semantic: bool, api_key: str | None) -> None:
        try:
            report = self._verifier(
                facts,
                output,
                semantic=semantic,
                api_key=api_key,
                status_callback=lambda value: self.events.put(("status", value)),
            )
            self.events.put(("verification_complete", report))
        except Exception as exc:
            self.events.put(("error", exc))
        finally:
            self._finish()
