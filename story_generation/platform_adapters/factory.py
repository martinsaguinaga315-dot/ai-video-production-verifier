"""Platform adapter lookup helpers."""
from __future__ import annotations

from story_generation.models.prompt_pack import PromptPackShot

from .base import PromptPlatformAdapter
from .generic import GenericPromptAdapter
from .jimeng import JimengPromptAdapter
from .kling import KlingPromptAdapter
from .models import PlatformPromptShot, PromptTargetPlatform
from .runway import RunwayPromptAdapter
from .veo import VeoPromptAdapter


_ADAPTERS: dict[PromptTargetPlatform, PromptPlatformAdapter] = {
    PromptTargetPlatform.GENERIC: GenericPromptAdapter(),
    PromptTargetPlatform.KLING: KlingPromptAdapter(),
    PromptTargetPlatform.JIMENG: JimengPromptAdapter(),
    PromptTargetPlatform.RUNWAY: RunwayPromptAdapter(),
    PromptTargetPlatform.VEO: VeoPromptAdapter(),
}


def get_platform_adapter(platform: PromptTargetPlatform | str) -> PromptPlatformAdapter:
    try:
        target = PromptTargetPlatform(platform)
    except ValueError as error:
        raise ValueError(f"Unknown prompt target platform: {platform!r}") from error
    return _ADAPTERS[target]


def adapt_prompt_shot(shot: PromptPackShot, platform: PromptTargetPlatform | str) -> PlatformPromptShot:
    return get_platform_adapter(platform).adapt_shot(shot)
