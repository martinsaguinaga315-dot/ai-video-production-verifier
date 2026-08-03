from __future__ import annotations

from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.clients.deepseek_client import DeepSeekClient
from story_generation.generators.creator_generator import CreatorGenerator
from story_generation.services.creator_pipeline_service import CreatorPipelineService
from story_generation.services.story_service import StoryService
from story_generation.services.story_validation_service import StoryValidationService


def build_creator_pipeline(
    *,
    api_key: str | None = None,
    model: str = "deepseek-chat",
    timeout: int = 45,
) -> CreatorPipelineService:
    """Assemble the production Creator pipeline without generating a story."""
    generator = CreatorGenerator(model=model)
    client = DeepSeekClient(api_key=api_key, model=model, timeout=timeout)
    story_service = StoryService(generator=generator, client=client)
    return CreatorPipelineService(
        story_service=story_service,
        storyboard_builder=StoryboardBuilder(),
        validation_service=StoryValidationService(),
    )
