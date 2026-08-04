from __future__ import annotations

from story_generation.models.bible import StoryBible
from story_generation.models.outline import PlotOutline

from .issues import GenerationIssue, GenerationIssueCode, issue, stable_sort_issues, validate_provenance


def validate_plot_outline(outline: PlotOutline, bible: StoryBible) -> list[GenerationIssue]:
    seen: set[str] = set()
    issues = validate_provenance(outline)
    for index, beat in enumerate(outline.beats):
        if beat.beat_id in seen:
            issues.append(issue(GenerationIssueCode.DUPLICATE_BEAT_ID, f"beats[{index}].beat_id", f"Duplicate beat id: {beat.beat_id}"))
        seen.add(beat.beat_id)
    sequences = [beat.sequence for beat in outline.beats]
    if len(set(sequences)) != len(sequences):
        issues.append(issue(GenerationIssueCode.DUPLICATE_SEQUENCE, "beats", "Duplicate beat sequence."))
    if sequences and set(sequences) != set(range(1, len(sequences) + 1)):
        issues.append(issue(GenerationIssueCode.NONCONTIGUOUS_SEQUENCE, "beats", "Beat sequences must be continuous."))
    character_ids = {item.character_id for item in bible.characters}
    location_ids = {item.location_id for item in bible.world.locations}
    for index, beat in enumerate(outline.beats):
        for ref in beat.characters:
            if ref.character_id not in character_ids:
                issues.append(issue(GenerationIssueCode.UNKNOWN_CHARACTER_REF, f"beats[{index}].characters", "Unknown character.", [ref.character_id]))
        if beat.location_id not in location_ids:
            issues.append(issue(GenerationIssueCode.UNKNOWN_LOCATION_REF, f"beats[{index}].location_id", "Unknown location.", [beat.location_id]))
    if outline.target_duration_s <= 0:
        issues.append(issue(GenerationIssueCode.INVALID_TARGET_DURATION, "target_duration_s", "Target duration must be positive."))
    return stable_sort_issues(issues)
