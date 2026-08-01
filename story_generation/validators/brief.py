from __future__ import annotations

from story_generation.models.brief import CreativeBrief
from story_generation.models.common import SourceKind

from .issues import ValidationIssue, issue


def validate_creative_brief(brief: CreativeBrief) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not brief.premise.strip():
        issues.append(issue("CREATIVE_IDEA_EMPTY", "premise", "Creative premise must not be empty."))
    if brief.target_duration_s <= 0:
        issues.append(issue("INVALID_TARGET_DURATION", "target_duration_s", "Target duration must be greater than zero."))
    if any(constraint.authoritative and not constraint.provenance.confirmed for constraint in brief.constraints):
        issues.append(issue(
            "UNCONFIRMED_AUTHORITATIVE_FIELD", "constraints",
            "Authoritative constraints require user confirmation.",
        ))
    if brief.provenance.source_kind is SourceKind.USER_CONFIRMED and not brief.provenance.confirmed:
        issues.append(issue("INVALID_PROVENANCE", "provenance", "Confirmed provenance must be marked confirmed."))
    return issues
