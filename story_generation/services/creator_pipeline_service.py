from __future__ import annotations


class CreatorPipelineService:
    """Orchestrate story generation, storyboard construction, and validation."""

    def __init__(
        self,
        story_service,
        storyboard_builder,
        validation_service,
    ):
        self.story_service = story_service
        self.storyboard_builder = storyboard_builder
        self.validation_service = validation_service

    def create(
        self,
        idea: str,
        style: str | None = None,
        goal: str | None = None,
    ):
        payload = self.story_service.create_story(idea, style, goal)
        storyboard = self.storyboard_builder.build(payload)
        return self.validation_service.validate(storyboard)
