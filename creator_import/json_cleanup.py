"""Conservative local cleanup for common LLM JSON wrappers."""
from __future__ import annotations

import json
import re
from typing import Any

from creator_import.extraction_errors import JsonStructureError


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_SIMPLE_SINGLE_QUOTE = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'")


def extract_json_object(text: str) -> str:
    """Return the first balanced JSON object/array, respecting string escapes."""
    fenced = _FENCE.search(text)
    source = fenced.group(1) if fenced else text
    start_positions = [index for index, char in enumerate(source) if char in "{["]
    for start in start_positions:
        if source[start] == '"':
            continue
        opener = source[start]
        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(source)):
            char = source[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return source[start : index + 1]
    raise JsonStructureError("模型返回格式不完整，无法找到完整JSON对象。")


def cleanup_json_text(text: str) -> str:
    candidate = extract_json_object(text).strip()
    candidate = candidate.replace("“", '"').replace("”", '"')
    candidate = candidate.replace("‘", "'").replace("’", "'")
    candidate = _TRAILING_COMMA.sub(r"\1", candidate)
    # This only handles simple quoted values. Complex malformed JSON is sent to
    # the bounded LLM repair step rather than being guessed locally.
    candidate = _SIMPLE_SINGLE_QUOTE.sub(lambda match: json.dumps(match.group(1)), candidate)
    return candidate


def load_clean_json(text: str) -> Any:
    try:
        return json.loads(cleanup_json_text(text))
    except JsonStructureError:
        raise
    except json.JSONDecodeError as exc:
        raise JsonStructureError("模型返回的JSON格式无效。") from exc
