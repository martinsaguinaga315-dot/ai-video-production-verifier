from __future__ import annotations

from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from creator_import.extraction_errors import ExtractionValidationError, JsonStructureError
from creator_import.json_cleanup import load_clean_json
from creator_import.prompt_templates import repair_user_prompt


ModelT = TypeVar("ModelT", bound=BaseModel)


def validation_summary(error: Exception) -> list[str]:
    if isinstance(error, ValidationError):
        return [
            ".".join(str(item) for item in issue["loc"]) + "：" + issue["msg"]
            for issue in error.errors()[:8]
        ]
    return ["模型返回格式不完整或不是合法JSON。"]


def parse_with_bounded_repair(
    raw_response: str,
    model_type: type[ModelT],
    repair_call: Callable[[str, list[str]], str],
    *,
    max_repairs: int = 2,
) -> ModelT:
    """Parse and validate with no more than two explicit repair calls."""
    current = raw_response
    problems: list[str] = []
    for repair_count in range(max_repairs + 1):
        try:
            return model_type.model_validate(load_clean_json(current))
        except (JsonStructureError, ValidationError) as exc:
            problems = validation_summary(exc)
            if repair_count >= max_repairs:
                raise ExtractionValidationError("自动结构化失败。", problems) from exc
            current = repair_call(current, problems)
    raise ExtractionValidationError("自动结构化失败。", problems)


def repair_with_client(client, invalid_response: str, problems: list[str]) -> str:
    return client.request_json(
        "你是JSON修复器。只修复格式和明确字段，不得编造事实，只返回JSON。",
        repair_user_prompt(invalid_response, problems),
    )
