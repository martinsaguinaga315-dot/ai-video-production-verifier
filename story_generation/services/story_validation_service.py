from __future__ import annotations

from math import isclose

from story_generation.models import (
    ArtifactType,
    GenerationIssue,
    GenerationIssueCode,
    GenerationResult,
    GenerationStatus,
    StoryboardDraft,
)
from story_generation.validators.issues import (
    calculate_duration_tolerance,
    issue,
    stable_sort_issues,
    validate_provenance,
)


class StoryValidationService:
    """Validate StoryboardDraft rules that do not need upstream artifacts."""

    def validate(self, storyboard: StoryboardDraft) -> GenerationResult:
        issues = validate_provenance(storyboard)
        shot_ids: set[str] = set()
        sequences: set[int] = set()
        ordered = sorted(
            storyboard.shots,
            key=lambda shot: (shot.start_time_s, shot.end_time_s, shot.sequence),
        )

        for index, shot in enumerate(storyboard.shots):
            path = f"shots[{index}]"
            if shot.shot_id in shot_ids:
                issues.append(issue(GenerationIssueCode.DUPLICATE_SHOT_ID, f"{path}.shot_id", "Duplicate shot id: {shot.shot_id}"))
            shot_ids.add(shot.shot_id)
            if shot.sequence in sequences:
                issues.append(issue(GenerationIssueCode.DUPLICATE_SEQUENCE, f"{path}.sequence", "Duplicate sequence."))
            sequences.add(shot.sequence)
            if shot.end_time_s <= shot.start_time_s:
                issues.append(issue(GenerationIssueCode.INVALID_TIME_RANGE, path, "Shot times must define a positive range."))
            elif not isclose(shot.duration_s, shot.end_time_s - shot.start_time_s, rel_tol=0.0, abs_tol=1e-6):
                issues.append(issue(GenerationIssueCode.DURATION_MISMATCH, f"{path}.duration_s", "Duration does not equal end minus start."))

        if sequences and sequences != set(range(1, len(sequences) + 1)):
            issues.append(issue(GenerationIssueCode.NONCONTIGUOUS_SEQUENCE, "shots", "Shot sequences must be continuous from 1."))
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_time_s < previous.end_time_s - 1e-6:
                issues.append(issue(GenerationIssueCode.SHOT_TIME_OVERLAP, "shots", f"Shots {previous.shot_id} and {current.shot_id} overlap."))

        tolerance = calculate_duration_tolerance(storyboard.target_duration_s)
        total_duration = sum(shot.duration_s for shot in storyboard.shots)
        if not isclose(total_duration, storyboard.target_duration_s, rel_tol=0.0, abs_tol=tolerance):
            issues.append(issue(GenerationIssueCode.DURATION_MISMATCH, "shots", "Storyboard duration does not match target."))

        sorted_issues = stable_sort_issues(issues)
        return GenerationResult(
            status=GenerationStatus.SUCCEEDED if not sorted_issues else GenerationStatus.FAILED,
            artifact_type=ArtifactType.STORYBOARD_DRAFT,
            artifact=storyboard,
            issues=sorted_issues,
        )
