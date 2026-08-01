from __future__ import annotations

from enum import StrEnum
from typing import Iterable

from pydantic import BaseModel

from story_generation.models.common import Constraint, FieldProvenance, SourceKind
from story_generation.models.generation import GenerationIssue, GenerationIssueCode


def issue(code: GenerationIssueCode, path: str, message: str, related_ids: list[str] | None = None) -> GenerationIssue:
    return GenerationIssue(code=code, severity="error", path=path, message=message, related_ids=related_ids or [])


def calculate_duration_tolerance(target_duration_s: float) -> float:
    return max(0.1, target_duration_s * 0.005)


def stable_sort_issues(issues: Iterable[GenerationIssue]) -> list[GenerationIssue]:
    return sorted(issues, key=lambda item: (item.path, item.code.value, item.related_ids))


def validate_provenance(value: object, path: str = "") -> list[GenerationIssue]:
    """Check provenance recursively without making any creative judgement."""
    issues: list[GenerationIssue] = []
    if isinstance(value, FieldProvenance):
        if value.source_kind is SourceKind.USER_CONFIRMED and not value.confirmed:
            issues.append(issue(GenerationIssueCode.INVALID_PROVENANCE, path, "User-confirmed provenance must be marked confirmed."))
        return issues
    if isinstance(value, Constraint) and value.authoritative and not value.provenance.confirmed:
        issues.append(issue(
            GenerationIssueCode.UNCONFIRMED_AUTHORITATIVE_FIELD, path,
            "Authoritative constraints require user confirmation.",
        ))
    if isinstance(value, BaseModel):
        for name in value.__class__.model_fields:
            child_path = f"{path}.{name}" if path else name
            issues.extend(validate_provenance(getattr(value, name), child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            issues.extend(validate_provenance(item, f"{path}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            issues.extend(validate_provenance(item, child_path))
    return issues


def validate_constraints(constraints: list[Constraint], path: str) -> list[GenerationIssue]:
    issues = validate_provenance(constraints, path)
    seen: set[str] = set()
    for index, constraint in enumerate(constraints):
        if constraint.constraint_id in seen:
            issues.append(issue(GenerationIssueCode.DUPLICATE_SEQUENCE, f"{path}[{index}].constraint_id", "Duplicate constraint id.", [constraint.constraint_id]))
        seen.add(constraint.constraint_id)
    return issues
