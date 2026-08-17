from __future__ import annotations

import pytest

from imagiframe_core import (
    PromptPackCreateRequest,
    StoryboardCreateRequest,
    StoryboardGenerationError,
    adapt_prompt_for_platform,
    create_prompt_pack,
    create_storyboard,
    verify_project,
)


def test_storyboard_facade_maps_public_contract_without_live_api():
    captured = {}
    sentinel = object()

    class FakePipeline:
        def create(self, **kwargs):
            captured["create"] = kwargs
            return sentinel

    def fake_factory(**kwargs):
        captured["factory"] = kwargs
        return FakePipeline()

    request = StoryboardCreateRequest(
        idea="  夜间雪场中的相遇  ",
        style="cinematic",
        goal="romantic",
        target_duration_s=8,
        aspect_ratio="16:9",
    )

    result = create_storyboard(
        request,
        api_key="test-only",
        model="fake-model",
        timeout=7,
        pipeline_factory=fake_factory,
    )

    assert result is sentinel
    assert captured["factory"] == {
        "api_key": "test-only",
        "timeout": 7,
        "model": "fake-model",
    }
    assert captured["create"] == {
        "idea": "夜间雪场中的相遇",
        "style": "cinematic",
        "goal": "romantic",
        "target_duration_s": 8.0,
        "aspect_ratio": "16:9",
    }


def test_storyboard_facade_wraps_internal_failure():
    def broken_factory(**_kwargs):
        raise RuntimeError("provider details must stay behind the facade")

    request = StoryboardCreateRequest(idea="test")

    with pytest.raises(StoryboardGenerationError) as exc_info:
        create_storyboard(request, pipeline_factory=broken_factory)

    assert exc_info.value.code == "storyboard_generation_failed"
    assert "provider details" not in str(exc_info.value)


def test_prompt_pack_facade_delegates_without_persistence():
    captured = {}
    sentinel = object()

    class FakePromptService:
        def generate(self, storyboard, **kwargs):
            captured["storyboard"] = storyboard
            captured["kwargs"] = kwargs
            return sentinel

    storyboard = object()
    request = PromptPackCreateRequest(
        shot_ids=["S01", "S02"],
        generation_target="generic",
        output_language="en",
    )

    result = create_prompt_pack(
        storyboard,
        request,
        service=FakePromptService(),
    )

    assert result is sentinel
    assert captured["storyboard"] is storyboard
    assert captured["kwargs"] == {
        "shot_ids": ["S01", "S02"],
        "generation_target": "generic",
        "output_language": "en",
    }


def test_platform_adapter_facade_is_prompt_only_and_injectable():
    captured = {}
    sentinel = object()
    shot = object()

    def fake_adapter(value, platform):
        captured["value"] = value
        captured["platform"] = platform
        return sentinel

    result = adapt_prompt_for_platform(
        shot,
        "kling",
        adapter_func=fake_adapter,
    )

    assert result is sentinel
    assert captured == {"value": shot, "platform": "kling"}


def test_verification_facade_delegates_in_memory_models():
    captured = {}
    sentinel = object()
    facts = object()
    director_output = object()

    def fake_runner(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return sentinel

    result = verify_project(
        facts,
        director_output,
        semantic=False,
        api_key=None,
        runner=fake_runner,
    )

    assert result is sentinel
    assert captured["args"] == (facts, director_output)
    assert captured["kwargs"]["semantic"] is False
    assert captured["kwargs"]["api_key"] is None
    assert captured["kwargs"]["status_callback"] is None


def test_blank_storyboard_idea_is_rejected_at_public_contract():
    with pytest.raises(ValueError):
        StoryboardCreateRequest(idea="   ")
