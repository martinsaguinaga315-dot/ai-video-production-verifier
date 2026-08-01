from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

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


class GenerationUsage(StrictModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None


class GenerationRequest(StrictModel):
    stage_name: str
    input_refs: list[str] = Field(default_factory=list)
    prompt_version: str
    request_id: str


class GenerationSettings(StrictModel):
    model: str
    thinking_mode: ThinkingMode = ThinkingMode.OFF
    temperature: float | None = None
    max_tokens: int
    timeout_s: float


class GenerationMetadata(StrictModel):
    request_id: str
    model: str
    prompt_version: str
    usage: GenerationUsage = Field(default_factory=GenerationUsage)
    finish_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class GenerationIssue(StrictModel):
    code: str
    severity: GenerationIssueSeverity
    path: str = ""
    message: str
    retryable: bool = False


class GenerationResult(StrictModel):
    status: GenerationStatus
    artifact_ref: str | None = None
    issues: list[GenerationIssue] = Field(default_factory=list)
    metadata: GenerationMetadata | None = None
    repair_of: str | None = None
