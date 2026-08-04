from __future__ import annotations

from math import isclose

from story_generation.models.bible import StoryBible
from story_generation.models.brief import CreativeBrief
from story_generation.models.scene import ScenePlan
from story_generation.models.storyboard import StoryboardDraft

from .issues import GenerationIssue, GenerationIssueCode, calculate_duration_tolerance, issue, stable_sort_issues, validate_provenance


def validate_storyboard_draft(
    storyboard: StoryboardDraft, brief: CreativeBrief, bible: StoryBible, plan: ScenePlan,
    *, duration_tolerance_s: float | None = None, time_epsilon_s: float = 1e-6,
) -> list[GenerationIssue]:
    issues = validate_provenance(storyboard)
    shot_ids: set[str] = set()
    sequences: set[int] = set()
    scene_ids = {scene.scene_id for scene in plan.scenes}
    character_ids = {character.character_id for character in bible.characters}
    location_ids = {location.location_id for location in bible.world.locations}
    prop_ids = {prop.prop_id for prop in bible.world.props}
    ordered = sorted(storyboard.shots, key=lambda shot: (shot.start_time_s, shot.end_time_s, shot.sequence))
    for index, shot in enumerate(storyboard.shots):
        path = f"shots[{index}]"
        if shot.shot_id in shot_ids:
            issues.append(issue(GenerationIssueCode.DUPLICATE_SHOT_ID, f"{path}.shot_id", f"Duplicate shot id: {shot.shot_id}"))
        shot_ids.add(shot.shot_id)
        if shot.sequence in sequences:
            issues.append(issue(GenerationIssueCode.DUPLICATE_SEQUENCE, f"{path}.sequence", f"Duplicate sequence: {shot.sequence}"))
        sequences.add(shot.sequence)
        if shot.scene_id not in scene_ids:
            issues.append(issue(GenerationIssueCode.UNKNOWN_SCENE_REF, f"{path}.scene_id", f"Unknown scene id: {shot.scene_id}"))
        if shot.location_id not in location_ids:
            issues.append(issue(GenerationIssueCode.UNKNOWN_LOCATION_REF, f"{path}.location_id", f"Unknown location id: {shot.location_id}"))
        if shot.end_time_s <= shot.start_time_s or shot.duration_s <= 0:
            issues.append(issue(GenerationIssueCode.INVALID_TIME_RANGE, path, "Shot times must define a positive range."))
        elif not isclose(shot.duration_s, shot.end_time_s - shot.start_time_s, rel_tol=0.0, abs_tol=time_epsilon_s):
            issues.append(issue(GenerationIssueCode.DURATION_MISMATCH, f"{path}.duration_s", "Duration does not equal end minus start."))
        for ref in shot.characters:
            if ref.character_id not in character_ids:
                issues.append(issue(GenerationIssueCode.UNKNOWN_CHARACTER_REF, f"{path}.characters", f"Unknown character id: {ref.character_id}"))
        for prop_id in shot.props:
            if prop_id not in prop_ids:
                issues.append(issue(GenerationIssueCode.UNKNOWN_PROP_REF, f"{path}.props", f"Unknown prop id: {prop_id}"))
    if sequences and sequences != set(range(1, len(sequences) + 1)):
        issues.append(issue(GenerationIssueCode.NONCONTIGUOUS_SEQUENCE, "shots", "Shot sequences must be continuous from 1."))
    for previous, current in zip(ordered, ordered[1:]):
        if current.start_time_s < previous.end_time_s - time_epsilon_s:
            issues.append(issue(GenerationIssueCode.SHOT_TIME_OVERLAP, "shots", f"Shots {previous.shot_id} and {current.shot_id} overlap."))
    for scene in plan.scenes:
        scene_duration = sum(shot.duration_s for shot in storyboard.shots if shot.scene_id == scene.scene_id)
        scene_tolerance = duration_tolerance_s if duration_tolerance_s is not None else calculate_duration_tolerance(scene.target_duration_s)
        if not isclose(scene_duration, scene.target_duration_s, rel_tol=0.0, abs_tol=scene_tolerance):
            issues.append(issue(GenerationIssueCode.SCENE_DURATION_MISMATCH, f"scenes[{scene.scene_id}]", "Scene shots do not match its target duration."))
    tolerance = duration_tolerance_s if duration_tolerance_s is not None else calculate_duration_tolerance(storyboard.target_duration_s)
    total = sum(shot.duration_s for shot in storyboard.shots)
    if not isclose(total, storyboard.target_duration_s, rel_tol=0.0, abs_tol=tolerance):
        issues.append(issue(GenerationIssueCode.DURATION_MISMATCH, "shots", "Storyboard duration does not match target."))
    shot_lookup = {shot.shot_id for shot in storyboard.shots}
    for index, shot in enumerate(storyboard.shots):
        for ref in shot.continuity_refs:
            if ref == shot.shot_id:
                issues.append(issue(GenerationIssueCode.SELF_SHOT_REFERENCE, f"shots[{index}].continuity_refs", "Shot cannot reference itself.", [ref]))
            if ref not in shot_lookup:
                issues.append(issue(GenerationIssueCode.UNKNOWN_SHOT_REF, f"shots[{index}].continuity_refs", "Unknown shot.", [ref]))
    for scene_id in scene_ids:
        ordered_scene = sorted((shot for shot in storyboard.shots if shot.scene_id == scene_id), key=lambda shot: shot.sequence)
        if any(current.start_time_s < previous.start_time_s - time_epsilon_s for previous, current in zip(ordered_scene, ordered_scene[1:])):
            issues.append(issue(GenerationIssueCode.INVALID_SHOT_ORDER, f"scenes[{scene_id}]", "Scene shot times regress by sequence."))
    return stable_sort_issues(issues)
