from __future__ import annotations

import threading
import time

from creator_desktop.analysis_controller import AnalysisController


def test_analysis_controller_prevents_duplicate_background_tasks() -> None:
    release = threading.Event()
    controller = AnalysisController(facts_extractor=lambda text, client: release.wait(1))
    assert controller.start_facts("剧本", object()) is True
    assert controller.start_facts("剧本", object()) is False
    release.set()
    deadline = time.time() + 2
    while controller.running and time.time() < deadline:
        time.sleep(0.01)
    assert controller.running is False
