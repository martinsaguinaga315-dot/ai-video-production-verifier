from __future__ import annotations

from math import isclose

from story_generation.models.bible import StoryBible
from story_generation.models.outline import PlotOutline
from story_generation.models.scene import ScenePlan

from .issues import ValidationIssue, issue, validate_provenance


def validate_scene_plan(plan: ScenePlan, bible: StoryBible, outline: PlotOutline) -> list[ValidationIssue]:
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
            issues.append(issue("DUPLICATE_SCENE_ID", f"{path}.scene_id", f"Duplicate scene id: {scene.scene_id}"))
        scene_ids.add(scene.scene_id)
        if scene.sequence in sequences:
            issues.append(issue("DUPLICATE_SEQUENCE", f"{path}.sequence", f"Duplicate sequence: {scene.sequence}"))
        sequences.add(scene.sequence)
        if scene.location_id not in location_ids:
            issues.append(issue("UNKNOWN_LOCATION_REF", f"{path}.location_id", f"Unknown location id: {scene.location_id}"))
        if scene.target_duration_s <= 0:
            issues.append(issue("INVALID_TIME_RANGE", f"{path}.target_duration_s", "Scene duration must be greater than zero."))
        for ref in scene.characters:
            if ref.character_id not in character_ids:
                issues.append(issue("UNKNOWN_CHARACTER_REF", f"{path}.characters", f"Unknown character id: {ref.character_id}"))
        for prop_id in scene.props:
            if prop_id not in prop_ids:
                issues.append(issue("UNKNOWN_PROP_REF", f"{path}.props", f"Unknown prop id: {prop_id}"))
        for beat_id in scene.required_beats:
            if beat_id not in beat_ids:
                issues.append(issue("UNKNOWN_BEAT_REF", f"{path}.required_beats", f"Unknown beat id: {beat_id}"))
    if sequences and sequences != set(range(1, len(sequences) + 1)):
        issues.append(issue("DUPLICATE_SEQUENCE", "scenes", "Scene sequences must be continuous from 1."))
    total = sum(scene.target_duration_s for scene in plan.scenes)
    if not isclose(total, plan.total_duration_s, rel_tol=0.0, abs_tol=0.1):
        issues.append(issue("SCENE_DURATION_MISMATCH", "total_duration_s", "Plan total does not equal scene durations."))
    return issues
