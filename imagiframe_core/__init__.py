"""Stable public facade for ImagiFrame Core consumers.

Web, Desktop, CLI, and future clients should prefer importing from this package
instead of depending on internal ``story_generation`` module paths.
"""

from .contracts import PromptPackCreateRequest, StoryboardCreateRequest
from .errors import (
    ImagiFrameCoreError,
    PromptAdapterError,
    PromptPackError,
    StoryboardGenerationError,
    VerificationFacadeError,
)
from .prompts import adapt_prompt_for_platform, create_prompt_pack
from .storyboards import create_storyboard
from .verification import verify_project

__all__ = [
    "ImagiFrameCoreError",
    "PromptAdapterError",
    "PromptPackCreateRequest",
    "PromptPackError",
    "StoryboardCreateRequest",
    "StoryboardGenerationError",
    "VerificationFacadeError",
    "adapt_prompt_for_platform",
    "create_prompt_pack",
    "create_storyboard",
    "verify_project",
]
