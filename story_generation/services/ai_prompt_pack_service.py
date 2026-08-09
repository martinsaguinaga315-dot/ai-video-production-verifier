"""DeepSeek-backed production prompt generation from storyboard facts."""
from __future__ import annotations

from story_generation.clients.deepseek_client import DeepSeekClient
from story_generation.models import PromptPack, PromptPackShot, StoryboardDraft
from story_generation.prompts.prompt_pack_prompts import SYSTEM_PROMPT, build_user_prompt


class AiPromptPackValidationError(ValueError):
    """DeepSeek returned JSON that is not a usable production prompt shot."""


class AiPromptPackService:
    def __init__(self, client: DeepSeekClient) -> None:
        self.client = client

    def generate(self, storyboard: StoryboardDraft, shot_ids: list[str] | None = None, output_language: str = "zh-CN", generation_target: str = "generic") -> PromptPack:
        if output_language not in {"zh-CN", "en"}:
            raise ValueError("output_language must be 'zh-CN' or 'en'")
        selected_ids = None if shot_ids is None else set(shot_ids)
        known_ids = {shot.shot_id for shot in storyboard.shots}
        if selected_ids is not None and (unknown := selected_ids - known_ids):
            raise ValueError(f"Unknown shot_id(s): {', '.join(sorted(unknown))}")
        selected = sorted((shot for shot in storyboard.shots if selected_ids is None or shot.shot_id in selected_ids), key=lambda item: item.sequence)
        generated = []
        for shot in selected:
            index = storyboard.shots.index(shot)
            response = self.client.generate_json(
                SYSTEM_PROMPT,
                build_user_prompt(
                    current=shot,
                    previous=storyboard.shots[index - 1] if index else None,
                    next_shot=storyboard.shots[index + 1] if index + 1 < len(storyboard.shots) else None,
                    output_language=output_language,
                    generation_target=generation_target,
                ),
                thinking=False,
                max_tokens=8192,
            )
            generated.append(self._validate_shot(response, shot, generation_target))
        return PromptPack(prompt_pack_id=f"prompt-pack-{storyboard.storyboard_id}-v{storyboard.version}", storyboard_id=storyboard.storyboard_id, storyboard_version=storyboard.version, generation_target=generation_target, output_language=output_language, provider="deepseek", model=self.client.model, shots=generated)

    @staticmethod
    def _validate_shot(response: dict, source, generation_target: str) -> PromptPackShot:
        required = ("shot_id", "first_frame_prompt", "end_frame_prompt", "video_prompt", "negative_prompt", "continuity_notes")
        if not isinstance(response, dict):
            raise AiPromptPackValidationError("DeepSeek returned an invalid prompt shot")
        normalized = {field: response[field] for field in required if field in response}
        normalized.setdefault("shot_id", source.shot_id)
        if normalized["shot_id"] != source.shot_id or any(field not in normalized for field in required):
            raise AiPromptPackValidationError("DeepSeek returned an invalid prompt shot")
        if any(not isinstance(response[field], str) or not response[field].strip() for field in required if field != "shot_id"):
            raise AiPromptPackValidationError("DeepSeek returned empty prompt fields")
        return PromptPackShot(scene_id=source.scene_id, sequence=source.sequence, generation_target=generation_target, **normalized)
