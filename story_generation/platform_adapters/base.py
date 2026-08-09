"""Common adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from story_generation.models.prompt_pack import PromptPackShot

from .models import PlatformPromptShot, PromptTargetPlatform


class PromptPlatformAdapter(ABC):
    platform: PromptTargetPlatform

    @abstractmethod
    def adapt_shot(self, shot: PromptPackShot) -> PlatformPromptShot:
        """Return a deterministic export without changing ``shot``."""
