from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from story_generation.models.common import Constraint, FieldProvenance, SourceKind


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def issue(code: str, path: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, path=path, message=message)


def validate_provenance(value: object, path: str = "") -> list[ValidationIssue]:
    """Check provenance recursively without making any creative judgement."""
    issues: list[ValidationIssue] = []
    if isinstance(value, FieldProvenance):
        if value.source_kind is SourceKind.USER_CONFIRMED and not value.confirmed:
            issues.append(issue("INVALID_PROVENANCE", path, "User-confirmed provenance must be marked confirmed."))
        return issues
    if isinstance(value, Constraint) and value.authoritative and not value.provenance.confirmed:
        issues.append(issue(
            "UNCONFIRMED_AUTHORITATIVE_FIELD", path,
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
