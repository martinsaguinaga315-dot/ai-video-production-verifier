from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Callable

from models import VerificationReport
from verification_service import run_verification


ControllerEvent = tuple[str, object]


class VerificationController:
    """Runs verification off the Tk main thread and posts queue events."""

    def __init__(
        self,
        runner: Callable[..., VerificationReport] = run_verification,
    ) -> None:
        self._runner = runner
        self.events: queue.Queue[ControllerEvent] = queue.Queue()
        self._running = False
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def start(
        self,
        facts_path: str | Path,
        director_output_path: str | Path,
        *,
        semantic: bool,
        api_key: str | None,
    ) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True

        worker = threading.Thread(
            target=self._run,
            args=(facts_path, director_output_path, semantic, api_key),
            daemon=True,
            name="verification-worker",
        )
        worker.start()
        return True

    def _run(
        self,
        facts_path: str | Path,
        director_output_path: str | Path,
        semantic: bool,
        api_key: str | None,
    ) -> None:
        try:
            report = self._runner(
                facts_path,
                director_output_path,
                semantic=semantic,
                api_key=api_key,
                status_callback=lambda status: self.events.put(("status", status)),
            )
            self.events.put(("complete", report))
        except Exception as exc:
            self.events.put(("error", exc))
        finally:
            with self._lock:
                self._running = False
