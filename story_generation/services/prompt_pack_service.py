"""Deterministic, offline prompt-pack generation from StoryboardDraft data."""
from __future__ import annotations

import re

from story_generation.models import PromptPack, PromptPackShot, StoryboardDraft, StoryboardShot


class PromptPackService:
    """Create production prompts without network, API, or story invention."""

    _GENERAL_NEGATIVE = (
        "Do not add unlisted characters or alter character identity or core wardrobe; "
        "do not add, remove, or transform key props; do not change the established location; "
        "do not use camera movement that conflicts with the shot description."
    )
    _GENERAL_NEGATIVE_ZH = "禁止无故增加人物或改变人物身份与核心服装特征；禁止关键道具无故出现、消失或变化；禁止改变既定场景结构；禁止出现与当前摄影机运动冲突的镜头变化。"
    _PLACEHOLDER_TEXT = {"state unspecified", "unspecified", "none specified"}
    _SYNTHETIC_LOCATION = re.compile(r"^(?:location|scene|scene-plan)-generated-[a-z0-9-]+$", re.IGNORECASE)

    @classmethod
    def _is_placeholder_text(cls, value: str | None) -> bool:
        return not value or value.strip().rstrip(".").casefold() in cls._PLACEHOLDER_TEXT

    @classmethod
    def _is_placeholder_location(cls, value: str | None) -> bool:
        return bool(value and cls._SYNTHETIC_LOCATION.fullmatch(value.strip()))

    @classmethod
    def _clean_prompt_value(cls, value: str | None) -> str:
        return "" if cls._is_placeholder_text(value) else (value or "").strip()

    @classmethod
    def _location(cls, shot: StoryboardShot) -> str:
        return "" if cls._is_placeholder_location(shot.location_id) else shot.location_id.strip()

    def generate(
        self,
        storyboard: StoryboardDraft,
        shot_ids: list[str] | None = None,
        generation_target: str = "generic",
        output_language: str = "zh-CN",
    ) -> PromptPack:
        """Generate all shots, or a validated ordered subset, from one storyboard."""
        if output_language not in {"zh-CN", "en"}:
            raise ValueError("output_language must be 'zh-CN' or 'en'")
        selected_ids = None if shot_ids is None else set(shot_ids)
        known_ids = {shot.shot_id for shot in storyboard.shots}
        if selected_ids is not None:
            unknown_ids = selected_ids - known_ids
            if unknown_ids:
                raise ValueError(f"Unknown shot_id(s): {', '.join(sorted(unknown_ids))}")
        selected = [shot for shot in storyboard.shots if selected_ids is None or shot.shot_id in selected_ids]
        selected.sort(key=lambda shot: shot.sequence)
        return PromptPack(
            prompt_pack_id=f"prompt-pack-{storyboard.storyboard_id}-v{storyboard.version}",
            storyboard_id=storyboard.storyboard_id,
            storyboard_version=storyboard.version,
            generation_target=generation_target,
            output_language=output_language,
            shots=[self._build_shot(shot, generation_target, output_language) for shot in selected],
        )

    def _build_shot(self, shot: StoryboardShot, generation_target: str, output_language: str) -> PromptPackShot:
        return PromptPackShot(
            shot_id=shot.shot_id,
            scene_id=shot.scene_id,
            sequence=shot.sequence,
            generation_target=generation_target,
            first_frame_prompt=self._first_frame(shot, output_language),
            end_frame_prompt=self._end_frame(shot, output_language),
            video_prompt=self._video(shot, output_language),
            negative_prompt=self._negative(shot, output_language),
            continuity_notes=self._continuity(shot, output_language),
        )

    @staticmethod
    def _joined(values: list[str]) -> str:
        return ", ".join(value.strip() for value in values if PromptPackService._clean_prompt_value(value))

    @staticmethod
    def _characters(shot: StoryboardShot) -> str:
        return ", ".join(character.character_id for character in shot.characters if PromptPackService._clean_prompt_value(character.character_id))

    def _first_frame(self, shot: StoryboardShot, language: str) -> str:
        opening, location = self._clean_prompt_value(shot.opening_state.description), self._location(shot)
        if language == "zh-CN":
            parts = [self._clean_prompt_value(shot.camera), f"场景位于{location}" if location else ""]
            if shot.characters:
                parts.append(f"{self._characters(shot)}处于镜头开始瞬间：{opening}" if opening else self._characters(shot))
            else:
                parts.append(opening)
            if shot.props: parts.append(f"关键道具为{self._joined(shot.props)}")
            if shot.first_frame_prompt: parts.append(f"画面保持{shot.first_frame_prompt}")
            if shot.continuity_refs: parts.append(f"与前后镜头保持{self._joined(shot.continuity_refs)}")
            return "。".join(part.strip("。 ") for part in parts if part) + "。"
        return (
            f"{shot.camera}. " + (f"At {location}, " if location else "") +
            (f"show {self._characters(shot)} in the opening moment: {opening}." if self._characters(shot) else (f"{opening}." if opening else "")) +
            (f" Props: {self._joined(shot.props)}." if self._joined(shot.props) else "") +
            (f" Visual seed: {shot.first_frame_prompt}." if self._clean_prompt_value(shot.first_frame_prompt) else "") +
            (f" Continuity: {self._joined(shot.continuity_refs)}." if self._joined(shot.continuity_refs) else "")
        )

    def _end_frame(self, shot: StoryboardShot, language: str) -> str:
        ending, location = self._clean_prompt_value(shot.ending_state.description), self._location(shot)
        if language == "zh-CN":
            parts = [f"镜头结束瞬间，{self._clean_prompt_value(shot.camera)}", f"场景仍位于{location}" if location else ""]
            parts.append(f"{self._characters(shot)}最终呈现：{ending}" if shot.characters and ending else ending)
            if shot.action: parts.append(f"动作完成结果为{shot.action}")
            if shot.performance: parts.append(f"表演最终保持{shot.performance}")
            if shot.props: parts.append(f"关键道具保持{self._joined(shot.props)}")
            if shot.continuity_refs: parts.append(f"为下一镜延续{self._joined(shot.continuity_refs)}")
            return "。".join(part.strip("。 ") for part in parts if part) + "。"
        return (
            f"Final frame of the shot, {shot.camera}. " + (f"At {location}, " if location else "") +
            (f"show {self._characters(shot)} at the ending moment: {ending}." if self._characters(shot) else (f"{ending}." if ending else "")) +
            (f" The completed action is {shot.action}." if self._clean_prompt_value(shot.action) else "") +
            (f" Performance settles as {shot.performance}." if self._clean_prompt_value(shot.performance) else "") +
            (f" Props remain consistent: {self._joined(shot.props)}." if self._joined(shot.props) else "") +
            (f" Required events completed: {self._joined(shot.required_events)}." if self._joined(shot.required_events) else "") +
            (f" Continuity into the next shot: {self._joined(shot.continuity_refs)}." if self._joined(shot.continuity_refs) else "")
        )

    def _video(self, shot: StoryboardShot, language: str) -> str:
        opening, ending = self._clean_prompt_value(shot.opening_state.description), self._clean_prompt_value(shot.ending_state.description)
        if language == "zh-CN":
            parts = [f"镜头持续 {shot.duration_s:g} 秒", f"从{opening}开始" if opening else ""]
            if shot.action: parts.append(f"人物动作：{shot.action}")
            if shot.performance: parts.append(f"表演状态：{shot.performance}")
            if shot.camera: parts.append(f"摄影机：{shot.camera}")
            if shot.required_events: parts.append(f"期间完成{self._joined(shot.required_events)}")
            if ending: parts.append(f"最终停在{ending}")
            if shot.video_prompt: parts.append(f"运动参考：{shot.video_prompt}")
            return "。".join(part.strip("。 ") for part in parts if part) + "。"
        return (
            f"Duration: {shot.duration_s:g} seconds." +
            (f" Opening state: {opening}." if opening else "") +
            (f" Action: {shot.action}." if self._clean_prompt_value(shot.action) else "") +
            (f" Performance: {shot.performance}." if self._clean_prompt_value(shot.performance) else "") +
            (f" Camera: {shot.camera}." if self._clean_prompt_value(shot.camera) else "") +
            (f" Required events: {self._joined(shot.required_events)}." if self._joined(shot.required_events) else "") +
            (f" Ending state: {ending}." if ending else "") +
            (f" Motion seed: {shot.video_prompt}." if self._clean_prompt_value(shot.video_prompt) else "")
        )

    def _negative(self, shot: StoryboardShot, language: str) -> str:
        general = self._GENERAL_NEGATIVE_ZH if language == "zh-CN" else self._GENERAL_NEGATIVE
        constraints = [*shot.negative_constraints, *shot.forbidden_events, general]
        return ("；" if language == "zh-CN" else " ").join(value for value in constraints if value.strip())

    def _continuity(self, shot: StoryboardShot, language: str) -> str:
        opening, ending = self._clean_prompt_value(shot.opening_state.description), self._clean_prompt_value(shot.ending_state.description)
        if language == "zh-CN":
            parts = [f"起始状态：{opening}" if opening else "", f"结束状态：{ending}" if ending else ""]
            if shot.characters: parts.append(f"人物保持{self._characters(shot)}")
            if shot.props: parts.append(f"道具保持{self._joined(shot.props)}")
            if shot.continuity_refs: parts.append(f"下一镜关联：{self._joined(shot.continuity_refs)}")
            if shot.required_events: parts.append(f"必须完成：{self._joined(shot.required_events)}")
            if shot.forbidden_events: parts.append(f"不得出现：{self._joined(shot.forbidden_events)}")
            return "。".join(part.strip("。 ") for part in parts if part) + "。"
        return (
            (f"Start: {opening}. " if opening else "") + (f"End: {ending}. " if ending else "") +
            (f"Characters: {self._characters(shot)}. " if self._characters(shot) else "") +
            (f"Props: {self._joined(shot.props)}. " if self._joined(shot.props) else "") +
            (f"Carry forward: {self._joined(shot.continuity_refs)}. " if self._joined(shot.continuity_refs) else "") +
            (f"Required events: {self._joined(shot.required_events)}. " if self._joined(shot.required_events) else "") +
            (f"Do not introduce: {self._joined(shot.forbidden_events)}." if self._joined(shot.forbidden_events) else "")
        )
