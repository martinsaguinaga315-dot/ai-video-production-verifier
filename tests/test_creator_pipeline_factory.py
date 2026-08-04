from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.clients.deepseek_client import DeepSeekClient
from story_generation.factories.creator_pipeline_factory import build_creator_pipeline
from story_generation.generators.creator_generator import CreatorGenerator
from story_generation.services.creator_pipeline_service import CreatorPipelineService
from story_generation.services.story_service import StoryService
from story_generation.services.story_validation_service import StoryValidationService


def test_factory_assembles_pipeline_with_explicit_client_configuration():
    pipeline = build_creator_pipeline(
        api_key="test-api-key",
        model="deepseek-test-model",
        timeout=12,
    )

    assert isinstance(pipeline, CreatorPipelineService)
    assert isinstance(pipeline.story_service, StoryService)
    assert isinstance(pipeline.story_service.generator, CreatorGenerator)
    assert isinstance(pipeline.story_service.client, DeepSeekClient)
    assert isinstance(pipeline.storyboard_builder, StoryboardBuilder)
    assert isinstance(pipeline.validation_service, StoryValidationService)
    assert pipeline.story_service.generator.model == "deepseek-test-model"
    assert pipeline.story_service.client.api_key == "test-api-key"
    assert pipeline.story_service.client.model == "deepseek-test-model"
    assert pipeline.story_service.client.timeout == 12


def test_factory_allows_client_to_read_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "environment-api-key")

    pipeline = build_creator_pipeline()

    assert pipeline.story_service.client.api_key == "environment-api-key"
