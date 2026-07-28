from __future__ import annotations

import pytest

from creator_import.extraction_errors import JsonStructureError
from creator_import.json_cleanup import load_clean_json


def test_extracts_fenced_json_and_surrounding_explanation() -> None:
    result = load_clean_json("说明如下：```json\n{\"title\": \"测试\"}\n```谢谢")
    assert result == {"title": "测试"}


def test_cleans_trailing_comma_and_simple_single_quotes() -> None:
    result = load_clean_json("{'title': '测试',}")
    assert result == {"title": "测试"}


def test_invalid_json_stops_safely() -> None:
    with pytest.raises(JsonStructureError):
        load_clean_json("这里没有JSON")
