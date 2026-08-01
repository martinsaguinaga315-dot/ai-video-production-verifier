from __future__ import annotations

from story_generation.models import (
    CharacterBible, CharacterRef, Constraint, CreativeBrief, FieldProvenance, LocationDefinition,
    PlotBeat, PlotOutline, SceneDefinition, ScenePlan, SourceKind, StoryBible,
    StoryboardDraft, StoryboardShot, WorldBible,
)
from story_generation.models.common import ShotState
from story_generation.validators import (
    validate_creative_brief, validate_generation_settings, validate_plot_outline, validate_scene_plan,
    validate_story_bible, validate_storyboard_draft,
)


def p() -> FieldProvenance:
    return FieldProvenance(source_kind=SourceKind.USER_CONFIRMED, confirmed=True)


def state() -> ShotState:
    return ShotState(description="still", provenance=p())


def bible() -> StoryBible:
    return StoryBible(
        logline="A reunion", characters=[CharacterBible(character_id="mia", name="Mia", role="lead", appearance="coat", provenance=p())],
        world=WorldBible(locations=[LocationDefinition(location_id="hall", name="Hall", description="quiet", provenance=p())], provenance=p()),
        provenance=p(),
    )


def brief() -> CreativeBrief:
    return CreativeBrief(premise="A reunion", format="short", target_duration_s=10, audience="general", provenance=p())


def test_brief_reports_empty_idea_and_invalid_duration() -> None:
    artifact = brief().model_copy(update={"premise": " ", "target_duration_s": 0})
    assert {item.code for item in validate_creative_brief(artifact)} == {"CREATIVE_IDEA_EMPTY", "INVALID_TARGET_DURATION"}


def test_brief_reports_unconfirmed_authority_and_invalid_provenance() -> None:
    artifact = brief().model_copy(update={
        "provenance": FieldProvenance(source_kind=SourceKind.USER_CONFIRMED),
        "constraints": [Constraint(constraint_id="c1", text="No violence", scope="story", authoritative=True, provenance=FieldProvenance(source_kind=SourceKind.AI_INFERENCE))],
    })
    assert {item.code for item in validate_creative_brief(artifact)} == {"INVALID_PROVENANCE", "UNCONFIRMED_AUTHORITATIVE_FIELD"}


def test_bible_and_outline_report_duplicate_ids() -> None:
    duplicate_bible = bible().model_copy(update={"characters": bible().characters * 2})
    outline = PlotOutline(beats=[PlotBeat(beat_id="b1", purpose="x", conflict="y", turn="z", provenance=p())] * 2, ending="end", provenance=p())
    assert "DUPLICATE_CHARACTER_ID" in {item.code for item in validate_story_bible(duplicate_bible)}
    assert "DUPLICATE_BEAT_ID" in {item.code for item in validate_plot_outline(outline)}


def test_scene_validator_checks_references_and_total_duration() -> None:
    outline = PlotOutline(beats=[], ending="end", provenance=p())
    scene = SceneDefinition(scene_id="s1", sequence=1, title="t", purpose="p", location_id="missing", time_context="night", target_duration_s=5, characters=[CharacterRef(character_id="missing", provenance=p())], props=["missing"], required_beats=["missing"], opening_state=state(), ending_state=state(), provenance=p())
    codes = {item.code for item in validate_scene_plan(ScenePlan(scenes=[scene], total_duration_s=4, provenance=p()), bible(), outline)}
    assert {"UNKNOWN_LOCATION_REF", "UNKNOWN_CHARACTER_REF", "UNKNOWN_PROP_REF", "UNKNOWN_BEAT_REF", "SCENE_DURATION_MISMATCH"} <= codes


def test_storyboard_validator_checks_time_duration_and_references() -> None:
    plan = ScenePlan(scenes=[SceneDefinition(scene_id="s1", sequence=1, title="t", purpose="p", location_id="hall", time_context="night", target_duration_s=10, opening_state=state(), ending_state=state(), provenance=p())], total_duration_s=10, provenance=p())
    shot = StoryboardShot(shot_id="sh1", scene_id="s1", sequence=1, start_time_s=0, end_time_s=5, duration_s=4, location_id="missing", characters=[CharacterRef(character_id="missing", provenance=p())], props=["missing"], opening_state=state(), action="walk", performance="quiet", ending_state=state(), camera="wide", first_frame_prompt="x", video_prompt="x", provenance=p())
    codes = {item.code for item in validate_storyboard_draft(StoryboardDraft(shots=[shot], version=1, provenance=p()), brief(), bible(), plan)}
    assert {"DURATION_MISMATCH", "UNKNOWN_LOCATION_REF", "UNKNOWN_CHARACTER_REF", "UNKNOWN_PROP_REF"} <= codes


def test_storyboard_validator_checks_scene_duration_and_unknown_scene() -> None:
    plan = ScenePlan(scenes=[SceneDefinition(scene_id="s1", sequence=1, title="t", purpose="p", location_id="hall", time_context="night", target_duration_s=10, opening_state=state(), ending_state=state(), provenance=p())], total_duration_s=10, provenance=p())
    shot = StoryboardShot(shot_id="sh1", scene_id="missing", sequence=1, start_time_s=0, end_time_s=10, duration_s=10, location_id="hall", opening_state=state(), action="walk", performance="quiet", ending_state=state(), camera="wide", first_frame_prompt="x", video_prompt="x", provenance=p())
    codes = {item.code for item in validate_storyboard_draft(StoryboardDraft(shots=[shot], version=1, provenance=p()), brief(), bible(), plan)}
    assert {"UNKNOWN_SCENE_REF", "SCENE_DURATION_MISMATCH"} <= codes


def test_generation_settings_validator_checks_deterministic_constraints() -> None:
    from story_generation.models import GenerationSettings, ThinkingMode

    settings = GenerationSettings(model="", thinking_mode=ThinkingMode.HIGH, temperature=0.2, max_tokens=0, timeout_s=0)
    assert {item.code for item in validate_generation_settings(settings)} == {"INVALID_GENERATION_SETTINGS"}
