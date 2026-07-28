from __future__ import annotations

import pytest
from pydantic import BaseModel

from creator_import.extraction_errors import ExtractionValidationError
from creator_import.json_repair import parse_with_bounded_repair


class Sample(BaseModel):
    title: str


def test_json_repair_runs_at_most_two_times() -> None:
    calls = []

    def repair(invalid, problems):
        calls.append((invalid, problems))
        return "{}"

    with pytest.raises(ExtractionValidationError):
        parse_with_bounded_repair("{}", Sample, repair)
    assert len(calls) == 2


def test_json_repair_accepts_second_response() -> None:
    responses = iter(['{"title":"已修复"}'])
    result = parse_with_bounded_repair("{}", Sample, lambda invalid, problems: next(responses))
    assert result.title == "已修复"
