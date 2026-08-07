from __future__ import annotations

from math import isclose

from story_generation.models import GenerationIssueCode, GenerationMetadata, GenerationStatus
from story_generation.validators.issues import calculate_duration_tolerance, issue


_REPAIRABLE_ISSUE_CODES = {"DURATION_MISMATCH", "SHOT_TIME_OVERLAP", "NONCONTIGUOUS_SEQUENCE"}


class CreatorPipelineService:
    """Orchestrate story generation, storyboard construction, and validation."""

    def __init__(
        self,
        story_service,
        storyboard_builder,
        validation_service,
    ):
        self.story_service = story_service
        self.storyboard_builder = storyboard_builder
        self.validation_service = validation_service

    def create(
        self,
        idea: str,
        style: str | None = None,
        goal: str | None = None,
        target_duration_s: float = 60,
        aspect_ratio: str = "16:9",
    ):
        # Keep the established default call shape compatible with existing
        # integrations; only pass settings when the user changed them.
        if target_duration_s == 60 and aspect_ratio == "16:9":
            payload = self.story_service.create_story(idea, style, goal)
        else:
            payload = self.story_service.create_story(
                idea,
                style,
                goal,
                target_duration_s=target_duration_s,
                aspect_ratio=aspect_ratio,
            )
        storyboard = self.storyboard_builder.build(payload)
        first_result = self.validation_service.validate(storyboard)
        self._validate_requested_duration(first_result, target_duration_s)
        first_request_id = storyboard.provenance.generation_request_id
        self._set_metadata(first_result, repair_count=0, parent_request_id=None)
        if first_result.status is GenerationStatus.SUCCEEDED or not self._can_repair(first_result.issues):
            return first_result

        repaired_payload = self.story_service.repair_storyboard(storyboard, first_result.issues, target_duration_s, first_request_id)
        repaired_storyboard = self.storyboard_builder.build(repaired_payload)
        repaired_result = self.validation_service.validate(repaired_storyboard)
        self._validate_requested_duration(repaired_result, target_duration_s)
        self._set_metadata(repaired_result, repair_count=1, parent_request_id=first_request_id)
        return repaired_result

    @staticmethod
    def _can_repair(issues) -> bool:
        return bool(issues) and all(issue.code.value in _REPAIRABLE_ISSUE_CODES for issue in issues)

    def _set_metadata(self, result, *, repair_count: int, parent_request_id: str | None) -> None:
        storyboard = result.artifact
        model = getattr(getattr(self.story_service, "generator", None), "model", "unknown")
        result.metadata = GenerationMetadata(
            request_id=storyboard.provenance.generation_request_id or "generated-storyboard",
            stage_name="storyboard_generation",
            model=model,
            prompt_version="storyboard-repair-v1" if repair_count else "storyboard-generation-v1",
            status=result.status,
            repair_count=repair_count,
            parent_request_id=parent_request_id,
        )

    @staticmethod
    def _validate_requested_duration(result, target_duration_s: float) -> None:
        storyboard = result.artifact
        tolerance = calculate_duration_tolerance(target_duration_s)
        if storyboard is None or not isclose(storyboard.target_duration_s, target_duration_s, rel_tol=0.0, abs_tol=tolerance):
            result.issues.append(issue(GenerationIssueCode.DURATION_MISMATCH, "target_duration_s", "Storyboard target duration does not match the requested duration."))
            result.status = GenerationStatus.FAILED
