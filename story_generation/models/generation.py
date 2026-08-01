from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import Field, model_validator

from .common import StrictModel


class ThinkingMode(StrEnum):
    OFF = "off"
    HIGH = "high"


class GenerationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationIssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ArtifactType(StrEnum):
    CREATIVE_BRIEF = "creative_brief"
    STORY_BIBLE = "story_bible"
    PLOT_OUTLINE = "plot_outline"
    SCENE_PLAN = "scene_plan"
    STORYBOARD_DRAFT = "storyboard_draft"
    VERIFICATION_REPORT = "verification_report"


class GenerationIssueCode(StrEnum):
    CREATIVE_IDEA_EMPTY = "CREATIVE_IDEA_EMPTY"
    INVALID_TARGET_DURATION = "INVALID_TARGET_DURATION"
    DUPLICATE_CHARACTER_ID = "DUPLICATE_CHARACTER_ID"
    DUPLICATE_LOCATION_ID = "DUPLICATE_LOCATION_ID"
    DUPLICATE_PROP_ID = "DUPLICATE_PROP_ID"
    DUPLICATE_BEAT_ID = "DUPLICATE_BEAT_ID"
    DUPLICATE_SCENE_ID = "DUPLICATE_SCENE_ID"
    DUPLICATE_SHOT_ID = "DUPLICATE_SHOT_ID"
    DUPLICATE_SEQUENCE = "DUPLICATE_SEQUENCE"
    NONCONTIGUOUS_SEQUENCE = "NONCONTIGUOUS_SEQUENCE"
    UNKNOWN_CHARACTER_REF = "UNKNOWN_CHARACTER_REF"
    UNKNOWN_LOCATION_REF = "UNKNOWN_LOCATION_REF"
    UNKNOWN_PROP_REF = "UNKNOWN_PROP_REF"
    UNKNOWN_BEAT_REF = "UNKNOWN_BEAT_REF"
    UNKNOWN_SCENE_REF = "UNKNOWN_SCENE_REF"
    UNKNOWN_SHOT_REF = "UNKNOWN_SHOT_REF"
    INVALID_TIME_RANGE = "INVALID_TIME_RANGE"
    SHOT_TIME_OVERLAP = "SHOT_TIME_OVERLAP"
    DURATION_MISMATCH = "DURATION_MISMATCH"
    SCENE_DURATION_MISMATCH = "SCENE_DURATION_MISMATCH"
    UNCONFIRMED_AUTHORITATIVE_FIELD = "UNCONFIRMED_AUTHORITATIVE_FIELD"
    INVALID_PROVENANCE = "INVALID_PROVENANCE"
    INVALID_GENERATION_SETTINGS = "INVALID_GENERATION_SETTINGS"


class GenerationUsage(StrictModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None


class GenerationRequest(StrictModel):
    request_id: str
    stage_name: str
    input_artifact_type: ArtifactType
    output_artifact_type: ArtifactType
    settings: "GenerationSettings"
    created_at: datetime
    parent_request_id: str | None = None


class GenerationSettings(StrictModel):
    quality_mode: str
    model: str
    thinking_mode: ThinkingMode = ThinkingMode.OFF
    temperature: float | None = None
    max_tokens: int
    timeout_s: float
    stream: bool = False
    max_retries: int = 0

    @model_validator(mode="after")
    def _validate_settings(self) -> "GenerationSettings":
        if not self.model or self.max_tokens <= 0 or self.timeout_s <= 0 or not 0 <= self.max_retries <= 3:
            raise ValueError("invalid generation settings")
        if self.temperature is not None and (not isfinite(self.temperature) or not 0 <= self.temperature <= 2):
            raise ValueError("temperature must be finite and between 0 and 2")
        if self.thinking_mode is ThinkingMode.HIGH and self.temperature is not None:
            raise ValueError("thinking mode requires temperature=None")
        return self


class GenerationMetadata(StrictModel):
    request_id: str
    stage_name: str
    model: str
    prompt_version: str
    status: GenerationStatus
    usage: GenerationUsage = Field(default_factory=GenerationUsage)
    finish_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    repair_count: int = 0
    parent_request_id: str | None = None


class GenerationIssue(StrictModel):
    code: GenerationIssueCode
    severity: GenerationIssueSeverity
    path: str = ""
    message: str
    related_ids: list[str] = Field(default_factory=list)
    suggestion: str = ""


class GenerationResult(StrictModel):
    status: GenerationStatus
    artifact_type: ArtifactType
    artifact: Any = None
    issues: list[GenerationIssue] = Field(default_factory=list)
    metadata: GenerationMetadata | None = None

    @model_validator(mode="after")
    def _validate_artifact(self) -> "GenerationResult":
        def json_safe(value: Any) -> bool:
            if value is None or isinstance(value, (str, int, float, bool, StrictModel)):
                return not isinstance(value, float) or isfinite(value)
            if isinstance(value, list):
                return all(json_safe(item) for item in value)
            if isinstance(value, dict):
                return all(isinstance(key, str) and json_safe(item) for key, item in value.items())
            return False
        if not json_safe(self.artifact):
            raise ValueError("artifact must be JSON-compatible or a domain model")
        return self
