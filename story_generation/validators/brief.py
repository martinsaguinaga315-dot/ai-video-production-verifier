from __future__ import annotations

from story_generation.models.brief import CreativeBrief
from story_generation.models.generation import GenerationSettings, ThinkingMode

from .issues import GenerationIssue, GenerationIssueCode, issue, stable_sort_issues, validate_constraints, validate_provenance


def validate_creative_brief(brief: CreativeBrief) -> list[GenerationIssue]:
    issues: list[GenerationIssue] = []
    if not brief.idea.strip():
        issues.append(issue(GenerationIssueCode.CREATIVE_IDEA_EMPTY, "idea", "Creative idea must not be empty."))
    if brief.target_duration_s <= 0:
        issues.append(issue(GenerationIssueCode.INVALID_TARGET_DURATION, "target_duration_s", "Target duration must be greater than zero."))
    issues.extend(validate_constraints(brief.constraints, "constraints"))
    issues.extend(validate_provenance(brief.field_provenance))
    return stable_sort_issues(issues)


def validate_generation_settings(settings: GenerationSettings) -> list[GenerationIssue]:
    issues: list[GenerationIssue] = []
    for path, invalid in (("model", not settings.model), ("quality_mode", not settings.quality_mode), ("max_tokens", settings.max_tokens <= 0), ("timeout_s", settings.timeout_s <= 0), ("max_retries", not 0 <= settings.max_retries <= 3)):
        if invalid: issues.append(issue(GenerationIssueCode.INVALID_GENERATION_SETTINGS, path, "Invalid generation setting."))
    if settings.thinking_mode is ThinkingMode.HIGH and settings.temperature is not None:
        issues.append(issue(GenerationIssueCode.INVALID_GENERATION_SETTINGS, "temperature", "Thinking mode requires temperature=None."))
    elif settings.temperature is not None and (not __import__("math").isfinite(settings.temperature) or not 0 <= settings.temperature <= 2):
        issues.append(issue(GenerationIssueCode.INVALID_GENERATION_SETTINGS, "temperature", "Temperature must be between 0 and 2."))
    return stable_sort_issues(issues)
