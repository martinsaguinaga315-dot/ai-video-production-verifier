from __future__ import annotations

from math import isclose

from story_generation.models.bible import StoryBible
from story_generation.models.outline import PlotOutline
from story_generation.models.scene import ScenePlan

from .issues import GenerationIssue, GenerationIssueCode, calculate_duration_tolerance, issue, stable_sort_issues, validate_provenance


def validate_scene_plan(plan: ScenePlan, bible: StoryBible, outline: PlotOutline, *, duration_tolerance_s: float | None = None) -> list[GenerationIssue]:
    issues = validate_provenance(plan)
    scene_ids: set[str] = set()
    sequences: set[int] = set()
    character_ids = {item.character_id for item in bible.characters}
    location_ids = {item.location_id for item in bible.world.locations}
    prop_ids = {item.prop_id for item in bible.world.props}
    beat_ids = {item.beat_id for item in outline.beats}
    for index, scene in enumerate(plan.scenes):
        path = f"scenes[{index}]"
        if scene.scene_id in scene_ids:
            issues.append(issue(GenerationIssueCode.DUPLICATE_SCENE_ID, f"{path}.scene_id", f"Duplicate scene id: {scene.scene_id}"))
        scene_ids.add(scene.scene_id)
        if scene.sequence in sequences:
            issues.append(issue(GenerationIssueCode.DUPLICATE_SEQUENCE, f"{path}.sequence", f"Duplicate sequence: {scene.sequence}"))
        sequences.add(scene.sequence)
        if scene.location_id not in location_ids:
            issues.append(issue(GenerationIssueCode.UNKNOWN_LOCATION_REF, f"{path}.location_id", f"Unknown location id: {scene.location_id}"))
        if scene.target_duration_s <= 0:
            issues.append(issue(GenerationIssueCode.INVALID_TIME_RANGE, f"{path}.target_duration_s", "Scene duration must be greater than zero."))
        for ref in scene.characters:
            if ref.character_id not in character_ids:
                issues.append(issue(GenerationIssueCode.UNKNOWN_CHARACTER_REF, f"{path}.characters", f"Unknown character id: {ref.character_id}"))
        for prop_id in scene.props:
            if prop_id not in prop_ids:
                issues.append(issue(GenerationIssueCode.UNKNOWN_PROP_REF, f"{path}.props", f"Unknown prop id: {prop_id}"))
        for beat_id in scene.required_beats:
            if beat_id not in beat_ids:
                issues.append(issue(GenerationIssueCode.UNKNOWN_BEAT_REF, f"{path}.required_beats", f"Unknown beat id: {beat_id}"))
    if sequences and sequences != set(range(1, len(sequences) + 1)):
        issues.append(issue(GenerationIssueCode.NONCONTIGUOUS_SEQUENCE, "scenes", "Scene sequences must be continuous from 1."))
    total = sum(scene.target_duration_s for scene in plan.scenes)
    tolerance = duration_tolerance_s if duration_tolerance_s is not None else calculate_duration_tolerance(plan.target_duration_s)
    if not isclose(total, plan.target_duration_s, rel_tol=0.0, abs_tol=tolerance):
        issues.append(issue(GenerationIssueCode.SCENE_DURATION_MISMATCH, "target_duration_s", "Plan total does not equal scene durations."))
    return stable_sort_issues(issues)
