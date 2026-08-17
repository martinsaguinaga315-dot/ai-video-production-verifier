"""Stable error boundary for ImagiFrame Core callers."""
from __future__ import annotations


class ImagiFrameCoreError(RuntimeError):
    """Base error safe for application-layer classification."""

    code = "imagiframe_core_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or self.code


class StoryboardGenerationError(ImagiFrameCoreError):
    code = "storyboard_generation_failed"


class PromptPackError(ImagiFrameCoreError):
    code = "prompt_pack_failed"


class PromptAdapterError(ImagiFrameCoreError):
    code = "prompt_adapter_failed"


class VerificationFacadeError(ImagiFrameCoreError):
    code = "verification_failed"
