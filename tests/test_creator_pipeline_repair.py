from story_generation.builders.storyboard_builder import StoryboardBuilder
from story_generation.models import GenerationIssue, GenerationIssueCode, GenerationStatus
from story_generation.prompts.storyboard_prompts import build_storyboard_repair_prompt
from story_generation.services.creator_pipeline_service import CreatorPipelineService
from story_generation.services.story_validation_service import StoryValidationService


def payload(durations, *, sequences=None, timing=None):
    sequences = sequences or list(range(1, len(durations) + 1))
    shots = []
    for index, (duration, sequence) in enumerate(zip(durations, sequences)):
        shot = {"sequence": sequence, "duration_s": duration}
        if timing:
            shot.update(timing[index])
        shots.append(shot)
    return {"target_duration_s": 60, "shots": shots}


class FakeStoryService:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.create_calls = []
        self.repair_calls = []

    def create_story(self, idea, style=None, goal=None):
        self.create_calls.append((idea, style, goal))
        return next(self.responses)

    def repair_storyboard(self, storyboard, issues, target_duration_s, parent_request_id=None):
        self.repair_calls.append((storyboard, issues, target_duration_s, parent_request_id))
        return next(self.responses)


def pipeline_for(*responses):
    service = FakeStoryService(responses)
    return CreatorPipelineService(service, StoryboardBuilder(), StoryValidationService()), service


def valid_payload():
    return payload([10] * 6)


def test_first_success_does_not_repair():
    pipeline, service = pipeline_for(valid_payload())
    result = pipeline.create("idea")
    assert result.status is GenerationStatus.SUCCEEDED
    assert len(service.create_calls) == 1
    assert service.repair_calls == []
    assert result.metadata.repair_count == 0


def test_duration_mismatch_is_repaired_once():
    pipeline, service = pipeline_for(payload([10] * 5), valid_payload())
    result = pipeline.create("idea")
    assert result.status is GenerationStatus.SUCCEEDED
    assert len(service.create_calls) == 1
    assert len(service.repair_calls) == 1
    assert result.metadata.repair_count == 1
    assert result.metadata.parent_request_id == service.repair_calls[0][3]


def test_second_failure_is_returned_without_a_third_call():
    pipeline, service = pipeline_for(payload([10] * 5), payload([10] * 4))
    result = pipeline.create("idea")
    assert result.status is GenerationStatus.FAILED
    assert len(service.create_calls) + len(service.repair_calls) == 2


def test_overlap_triggers_repair():
    initial = payload([30, 30], timing=[
        {"start_time_s": 0, "end_time_s": 30},
        {"start_time_s": 20, "end_time_s": 50},
    ])
    pipeline, service = pipeline_for(initial, valid_payload())
    assert pipeline.create("idea").status is GenerationStatus.SUCCEEDED
    assert len(service.repair_calls) == 1


def test_noncontiguous_sequence_triggers_repair():
    pipeline, service = pipeline_for(payload([10] * 6, sequences=[1, 2, 4, 5, 6, 7]), valid_payload())
    assert pipeline.create("idea").status is GenerationStatus.SUCCEEDED
    assert len(service.repair_calls) == 1


def test_non_repairable_issue_does_not_repair():
    initial = {"target_duration_s": 61, "shots": [{"sequence": 1, "duration_s": 60, "shot_id": "same"}, {"sequence": 2, "duration_s": 1, "shot_id": "same"}]}
    pipeline, service = pipeline_for(initial)
    result = pipeline.create("idea")
    assert result.status is GenerationStatus.FAILED
    assert service.repair_calls == []


def test_mixed_repairable_and_non_repairable_issues_do_not_repair():
    initial = {"target_duration_s": 60, "shots": [{"sequence": 1, "duration_s": 50, "shot_id": "same"}, {"sequence": 2, "duration_s": 1, "shot_id": "same"}]}
    pipeline, service = pipeline_for(initial)
    result = pipeline.create("idea")
    assert result.status is GenerationStatus.FAILED
    assert {issue.code.value for issue in result.issues} >= {"DURATION_MISMATCH", "DUPLICATE_SHOT_ID"}
    assert service.repair_calls == []


def test_repair_prompt_includes_sanitized_storyboard_issue_and_contract():
    storyboard = StoryboardBuilder().build(valid_payload())
    issue = GenerationIssue(code=GenerationIssueCode.DURATION_MISMATCH, severity="error", message="total is wrong")
    prompt = build_storyboard_repair_prompt(storyboard, [issue], 60, "first-request")
    assert '"shots"' in prompt
    assert "DURATION_MISMATCH" in prompt and "total is wrong" in prompt
    assert "60 秒" in prompt and "完整替换" in prompt
    assert '"provenance"' not in prompt
    assert "first-request" in prompt


def test_repair_does_not_scale_model_durations():
    initial = payload([10] * 5)
    pipeline, _ = pipeline_for(initial, initial)
    result = pipeline.create("idea")
    assert sum(shot.duration_s for shot in result.artifact.shots) == 50
    assert {issue.code.value for issue in result.issues} == {"DURATION_MISMATCH"}
