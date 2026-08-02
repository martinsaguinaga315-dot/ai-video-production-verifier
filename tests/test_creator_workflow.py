from __future__ import annotations

import json

from creator_desktop.analysis_controller import AnalysisController
from creator_import.facts_extractor import extract_facts_from_text
from tests.test_director_parser import director_payload
from tests.test_facts_extractor import MockClient, facts_payload
from verification_service import run_verification_models


def test_confirmed_models_can_run_local_verification_in_memory() -> None:
    facts = extract_facts_from_text("文本", MockClient([json.dumps(facts_payload(), ensure_ascii=False)]))
    from creator_import.director_parser import parse_director_output_from_text

    output = parse_director_output_from_text("分镜", facts, MockClient([json.dumps(director_payload(), ensure_ascii=False)]))
    report = run_verification_models(facts, output)
    assert report.score >= 0


def test_creator_controller_emits_facts_ready_without_real_api() -> None:
    controller = AnalysisController(facts_extractor=lambda text, client: "facts")
    assert controller.start_facts("剧本", object())
    kind, payload = controller.events.get(timeout=1)
    assert kind == "status"
    kind, payload = controller.events.get(timeout=1)
    assert (kind, payload) == ("facts_ready", "facts")
