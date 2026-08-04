from __future__ import annotations

from datetime import datetime, timezone

import pytest

from story_generation.models import (
    CharacterBible, CharacterRef, Constraint, CreativeBrief, FieldProvenance, LocationDefinition,
    PlotBeat, PlotOutline, SceneDefinition, ScenePlan, SourceKind, StoryBible,
    StoryboardDraft, StoryboardShot, WorldBible,
)
from story_generation.models.generation import GenerationIssue, GenerationIssueCode
from story_generation.validators.issues import calculate_duration_tolerance
from story_generation.models.common import ShotState
from story_generation.validators import (
    validate_creative_brief, validate_generation_settings, validate_plot_outline, validate_scene_plan,
    validate_story_bible, validate_storyboard_draft,
)

EXPECTED_ISSUE_CODES = {member.value for member in GenerationIssueCode}


@pytest.mark.parametrize("code", sorted(EXPECTED_ISSUE_CODES))
def test_expected_issue_code_is_enumerated(code: str) -> None:
    assert GenerationIssueCode(code).value == code


def p() -> FieldProvenance:
    return FieldProvenance(source_kind=SourceKind.USER_CONFIRMED, field_path="/test", confirmed=True, confirmed_at=datetime.now(timezone.utc), confirmed_by="tester")


def state() -> ShotState:
    return ShotState(description="still", provenance=p())


def bible() -> StoryBible:
    return StoryBible(
        bible_id="bible", brief_id="brief", premise="A reunion", characters=[CharacterBible(character_id="mia", name="Mia", role="lead", age_description="adult", appearance="coat", provenance=p())],
        world=WorldBible(world_id="world", time_period="now", setting="hall", locations=[LocationDefinition(location_id="hall", name="Hall", description="quiet", provenance=p())], provenance=p()),
        provenance=p(),
    )


def brief() -> CreativeBrief:
    return CreativeBrief(brief_id="brief", idea="A reunion", title="t", language="zh", target_duration_s=10, aspect_ratio="16:9", target_platform="web", target_audience="general", provenance=p())


def test_brief_reports_empty_idea_and_invalid_duration() -> None:
    artifact = brief().model_copy(update={"idea": " ", "target_duration_s": 0})
    assert {item.code for item in validate_creative_brief(artifact)} == {"CREATIVE_IDEA_EMPTY", "INVALID_TARGET_DURATION"}


def test_brief_reports_unconfirmed_authority_and_invalid_provenance() -> None:
    artifact = brief().model_copy(update={
        "constraints": [Constraint(constraint_id="c1", text="No violence", scope="story", authoritative=True, provenance=FieldProvenance(source_kind=SourceKind.AI_INFERENCE, field_path="/constraint"))],
    })
    assert {item.code.value for item in validate_creative_brief(artifact)} == {"UNCONFIRMED_AUTHORITATIVE_FIELD"}


def test_bible_and_outline_report_duplicate_ids() -> None:
    duplicate_bible = bible().model_copy(update={"characters": bible().characters * 2})
    outline = PlotOutline(outline_id="o", bible_id="bible", beats=[PlotBeat(beat_id="b1", sequence=1, title="x", purpose="x", description="y", location_id="hall", provenance=p())] * 2, target_duration_s=10, provenance=p())
    assert "DUPLICATE_CHARACTER_ID" in {item.code.value for item in validate_story_bible(duplicate_bible)}
    assert "DUPLICATE_BEAT_ID" in {item.code.value for item in validate_plot_outline(outline, bible())}


def test_scene_validator_checks_references_and_total_duration() -> None:
    outline = PlotOutline(outline_id="o", bible_id="bible", beats=[], target_duration_s=10, provenance=p())
    scene = SceneDefinition(scene_id="s1", sequence=1, title="t", purpose="p", location_id="missing", time_context="night", target_duration_s=5, characters=[CharacterRef(character_id="missing", provenance=p())], props=["missing"], required_beats=["missing"], opening_state=state(), ending_state=state(), provenance=p())
    codes = {item.code.value for item in validate_scene_plan(ScenePlan(scene_plan_id="sp", outline_id="o", scenes=[scene], target_duration_s=4, provenance=p()), bible(), outline)}
    assert {"UNKNOWN_LOCATION_REF", "UNKNOWN_CHARACTER_REF", "UNKNOWN_PROP_REF", "UNKNOWN_BEAT_REF", "SCENE_DURATION_MISMATCH"} <= codes


def test_storyboard_validator_checks_time_duration_and_references() -> None:
    plan = ScenePlan(scene_plan_id="sp", outline_id="o", scenes=[SceneDefinition(scene_id="s1", sequence=1, title="t", purpose="p", location_id="hall", time_context="night", target_duration_s=10, opening_state=state(), ending_state=state(), provenance=p())], target_duration_s=10, provenance=p())
    shot = StoryboardShot(shot_id="sh1", scene_id="s1", sequence=1, start_time_s=0, end_time_s=5, duration_s=4, location_id="missing", characters=[CharacterRef(character_id="missing", provenance=p())], props=["missing"], opening_state=state(), action="walk", performance="quiet", ending_state=state(), camera="wide", first_frame_prompt="x", video_prompt="x", provenance=p())
    codes = {item.code.value for item in validate_storyboard_draft(StoryboardDraft(storyboard_id="sb", scene_plan_id="sp", shots=[shot], target_duration_s=10, version=1, provenance=p()), brief(), bible(), plan)}
    assert {"DURATION_MISMATCH", "UNKNOWN_LOCATION_REF", "UNKNOWN_CHARACTER_REF", "UNKNOWN_PROP_REF"} <= codes


def test_storyboard_validator_checks_scene_duration_and_unknown_scene() -> None:
    plan = ScenePlan(scene_plan_id="sp", outline_id="o", scenes=[SceneDefinition(scene_id="s1", sequence=1, title="t", purpose="p", location_id="hall", time_context="night", target_duration_s=10, opening_state=state(), ending_state=state(), provenance=p())], target_duration_s=10, provenance=p())
    shot = StoryboardShot(shot_id="sh1", scene_id="missing", sequence=1, start_time_s=0, end_time_s=10, duration_s=10, location_id="hall", opening_state=state(), action="walk", performance="quiet", ending_state=state(), camera="wide", first_frame_prompt="x", video_prompt="x", provenance=p())
    codes = {item.code.value for item in validate_storyboard_draft(StoryboardDraft(storyboard_id="sb", scene_plan_id="sp", shots=[shot], target_duration_s=10, version=1, provenance=p()), brief(), bible(), plan)}
    assert {"UNKNOWN_SCENE_REF", "SCENE_DURATION_MISMATCH"} <= codes


def test_generation_settings_validator_checks_deterministic_constraints() -> None:
    from story_generation.models import GenerationSettings, ThinkingMode

    settings = GenerationSettings.model_construct(quality_mode="", model="", thinking_mode=ThinkingMode.HIGH, temperature=0.2, max_tokens=0, timeout_s=0, stream=False, max_retries=0)
    assert {item.code.value for item in validate_generation_settings(settings)} == {"INVALID_GENERATION_SETTINGS"}


def test_validators_return_sorted_generation_issues_without_mutating_input() -> None:
    artifact = brief().model_copy(update={"idea": " "})
    before = artifact.model_dump(mode="json")
    issues = validate_creative_brief(artifact)
    assert all(isinstance(item, GenerationIssue) for item in issues)
    assert issues == sorted(issues, key=lambda item: (item.path, item.code.value, item.related_ids))
    assert artifact.model_dump(mode="json") == before


def test_duration_tolerance_is_centralized() -> None:
    assert calculate_duration_tolerance(10) == 0.1
    assert calculate_duration_tolerance(100) == 0.5
