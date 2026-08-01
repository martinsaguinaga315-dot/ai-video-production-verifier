from __future__ import annotations

from story_generation.models.brief import CreativeBrief
from story_generation.models.generation import GenerationSettings, ThinkingMode

from .issues import ValidationIssue, issue, validate_provenance


def validate_creative_brief(brief: CreativeBrief) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not brief.premise.strip():
        issues.append(issue("CREATIVE_IDEA_EMPTY", "premise", "Creative premise must not be empty."))
    if brief.target_duration_s <= 0:
        issues.append(issue("INVALID_TARGET_DURATION", "target_duration_s", "Target duration must be greater than zero."))
    issues.extend(validate_provenance(brief))
    return issues


def validate_generation_settings(settings: GenerationSettings) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not settings.model or settings.max_tokens <= 0 or settings.timeout_s <= 0:
        issues.append(issue("INVALID_GENERATION_SETTINGS", "settings", "Model, max_tokens, and timeout_s must be valid."))
    if settings.thinking_mode is ThinkingMode.HIGH and settings.temperature is not None:
        issues.append(issue("INVALID_GENERATION_SETTINGS", "temperature", "Thinking mode requires temperature=None."))
    elif settings.temperature is not None and not 0 <= settings.temperature <= 2:
        issues.append(issue("INVALID_GENERATION_SETTINGS", "temperature", "Temperature must be between 0 and 2."))
    return issues
