"""Public request contracts for the ImagiFrame Core facade."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _CoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StoryboardCreateRequest(_CoreRequest):
    """Stable input contract for storyboard generation."""

    idea: str = Field(min_length=1)
    style: str | None = None
    goal: str | None = None
    target_duration_s: float = Field(default=60, gt=0)
    aspect_ratio: str = Field(default="16:9", min_length=1)

    @field_validator("idea")
    @classmethod
    def _idea_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("idea must not be blank")
        return cleaned


class PromptPackCreateRequest(_CoreRequest):
    """Stable input contract for deterministic prompt-pack creation."""

    shot_ids: list[str] | None = None
    generation_target: str = Field(default="generic", min_length=1)
    output_language: Literal["zh-CN", "en"] = "zh-CN"

    @field_validator("shot_ids")
    @classmethod
    def _shot_ids_not_blank(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("shot_ids must not contain blank values")
        return cleaned
