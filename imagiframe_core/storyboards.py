"""Storyboard facade over the existing story-generation pipeline."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .contracts import StoryboardCreateRequest
from .errors import StoryboardGenerationError


def create_storyboard(
    request: StoryboardCreateRequest,
    *,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int = 45,
    pipeline_factory: Callable[..., Any] | None = None,
) -> Any:
    """Generate and validate one storyboard through the existing Core pipeline.

    ``pipeline_factory`` is injectable so tests and application layers can keep
    the facade offline. When omitted, the current production
    ``build_creator_pipeline`` factory is resolved lazily.
    """
    if pipeline_factory is None:
        from story_generation.clients.deepseek_client import DEFAULT_DEEPSEEK_MODEL
        from story_generation.factories.creator_pipeline_factory import build_creator_pipeline

        pipeline_factory = build_creator_pipeline
        model = model or DEFAULT_DEEPSEEK_MODEL

    factory_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "timeout": timeout,
    }
    if model is not None:
        factory_kwargs["model"] = model

    try:
        pipeline = pipeline_factory(**factory_kwargs)
        return pipeline.create(
            idea=request.idea,
            style=request.style,
            goal=request.goal,
            target_duration_s=request.target_duration_s,
            aspect_ratio=request.aspect_ratio,
        )
    except StoryboardGenerationError:
        raise
    except Exception as exc:
        raise StoryboardGenerationError(
            "ImagiFrame Core could not generate the storyboard."
        ) from exc
