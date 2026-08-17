"""Prompt-pack and prompt-platform facade helpers."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .contracts import PromptPackCreateRequest
from .errors import PromptAdapterError, PromptPackError


def create_prompt_pack(
    storyboard: Any,
    request: PromptPackCreateRequest | None = None,
    *,
    service: Any | None = None,
) -> Any:
    """Create a deterministic Prompt Pack without adding persistence concerns."""
    request = request or PromptPackCreateRequest()

    if service is None:
        from story_generation.services.prompt_pack_service import PromptPackService

        service = PromptPackService()

    try:
        return service.generate(
            storyboard,
            shot_ids=request.shot_ids,
            generation_target=request.generation_target,
            output_language=request.output_language,
        )
    except PromptPackError:
        raise
    except Exception as exc:
        raise PromptPackError(
            "ImagiFrame Core could not create the prompt pack."
        ) from exc


def adapt_prompt_for_platform(
    shot: Any,
    platform: str,
    *,
    adapter_func: Callable[[Any, str], Any] | None = None,
) -> Any:
    """Adapt one canonical Prompt Pack shot for a target platform.

    This is prompt adaptation only. It does not submit a generation job and is
    intentionally separate from future Kling/Jimeng/Veo generation providers.
    """
    if adapter_func is None:
        from story_generation.platform_adapters import adapt_prompt_shot

        adapter_func = adapt_prompt_shot

    try:
        return adapter_func(shot, platform)
    except PromptAdapterError:
        raise
    except Exception as exc:
        raise PromptAdapterError(
            f"ImagiFrame Core could not adapt the prompt for platform {platform!r}."
        ) from exc
