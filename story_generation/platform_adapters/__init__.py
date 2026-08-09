"""Pure, non-persistent platform prompt adapters."""
from .base import PromptPlatformAdapter
from .factory import adapt_prompt_shot, get_platform_adapter
from .models import PlatformPromptShot, PromptTargetPlatform

__all__ = ["PlatformPromptShot", "PromptPlatformAdapter", "PromptTargetPlatform", "adapt_prompt_shot", "get_platform_adapter"]
