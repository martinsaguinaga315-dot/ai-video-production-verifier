from __future__ import annotations

from story_generation.models.outline import PlotOutline

from .issues import ValidationIssue, issue, validate_provenance


def validate_plot_outline(outline: PlotOutline) -> list[ValidationIssue]:
    seen: set[str] = set()
    issues = validate_provenance(outline)
    for index, beat in enumerate(outline.beats):
        if beat.beat_id in seen:
            issues.append(issue("DUPLICATE_BEAT_ID", f"beats[{index}].beat_id", f"Duplicate beat id: {beat.beat_id}"))
        seen.add(beat.beat_id)
    return issues
