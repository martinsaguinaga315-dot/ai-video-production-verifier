from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from story_generation.models import StoryboardDraft


class StoryboardBuilder:
    """Build a validated storyboard draft from a DeepSeek JSON object."""

    def build(self, payload: dict[str, Any]) -> StoryboardDraft:
        if not isinstance(payload, dict):
            raise TypeError("Storyboard payload must be a JSON object")
        request_id = self._generation_request_id(payload)
        raw_shots = self._raw_shots(payload)
        if not isinstance(raw_shots, list):
            raise TypeError("Storyboard shots must be a list")
        shots: list[dict[str, Any]] = []
        previous_end_time: float | None = None
        for index, shot in enumerate(raw_shots):
            built_shot = self._build_shot(shot, index, request_id, previous_end_time)
            shots.append(built_shot)
            previous_end_time = built_shot["end_time_s"]

        draft_data = {
            "storyboard_id": payload.get("storyboard_id") or f"storyboard-{request_id}",
            "scene_plan_id": payload.get("scene_plan_id") or f"scene-plan-{request_id}",
            "target_duration_s": payload.get("target_duration_s", 60.0),
            "version": payload.get("version", 1),
            "provenance": self._provenance("/storyboard", request_id),
            "shots": shots,
        }
        return StoryboardDraft.model_validate(draft_data)

    @staticmethod
    def _raw_shots(payload: dict[str, Any]) -> list[Any]:
        """Read known DeepSeek storyboard wrappers without changing shot data."""
        if "shots" in payload:
            raw_shots = payload["shots"]
        else:
            storyboard = payload.get("storyboard", [])
            if isinstance(storyboard, list):
                raw_shots = storyboard
            elif isinstance(storyboard, dict):
                if "shots" in storyboard:
                    raw_shots = storyboard["shots"]
                elif isinstance(storyboard.get("scenes"), list):
                    raw_shots = []
                    for scene in storyboard["scenes"]:
                        if isinstance(scene, dict) and isinstance(scene.get("shots"), list):
                            raw_shots.extend(scene["shots"])
                else:
                    raw_shots = []
            else:
                raw_shots = []
        if not isinstance(raw_shots, list):
            raise TypeError("Storyboard shots must be a list")
        return raw_shots

    @staticmethod
    def _generation_request_id(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return f"generated-{sha256(canonical.encode()).hexdigest()[:12]}"

    @staticmethod
    def _provenance(field_path: str, request_id: str) -> dict[str, str]:
        return {"source_kind": "generated", "field_path": field_path, "generation_request_id": request_id}

    def _build_shot(
        self,
        raw_shot: Any,
        index: int,
        request_id: str,
        previous_end_time: float | None,
    ) -> dict[str, Any]:
        if not isinstance(raw_shot, dict):
            raise TypeError("Each storyboard shot must be a JSON object")
        start_time = raw_shot.get("start_time_s")
        if start_time is None:
            start_time = previous_end_time if previous_end_time is not None else 0.0
        end_time = raw_shot.get("end_time_s")
        duration = raw_shot.get("duration_s")
        if duration is None:
            duration = raw_shot.get("duration")
        if duration is None:
            duration = end_time - start_time if end_time is not None and end_time > start_time else 5.0
        if end_time is None:
            end_time = start_time + duration
        sequence = raw_shot.get("sequence")
        if sequence is None:
            sequence = raw_shot.get("shot_number")
        if sequence is None:
            sequence = raw_shot.get("shot")
        if sequence is None:
            sequence = index + 1
        path = f"/shots/{index}"
        return {
            "shot_id": raw_shot.get("shot_id") or f"shot-{index + 1:03d}",
            "scene_id": raw_shot.get("scene_id") or "scene-generated-001",
            "sequence": sequence,
            "start_time_s": start_time,
            "end_time_s": end_time,
            "duration_s": duration,
            "location_id": raw_shot.get("location_id") or "location-generated-001",
            "characters": [self._build_character(item, f"{path}/characters/{i}", request_id, i) for i, item in enumerate(raw_shot.get("characters", []))],
            "props": raw_shot.get("props", []),
            "opening_state": self._build_state(raw_shot.get("opening_state"), f"{path}/opening_state", request_id),
            "action": raw_shot.get("action") or "No action specified.",
            "performance": raw_shot.get("performance") or "Natural performance.",
            "dialogue": [self._build_dialogue(item, f"{path}/dialogue/{i}", request_id) for i, item in enumerate(raw_shot.get("dialogue", []))],
            "sound": self._build_sound(raw_shot),
            "ending_state": self._build_state(raw_shot.get("ending_state"), f"{path}/ending_state", request_id),
            "camera": raw_shot.get("camera") or "Static medium shot.",
            "first_frame_prompt": raw_shot.get("first_frame_prompt") or "Cinematic storyboard frame.",
            "video_prompt": raw_shot.get("video_prompt") or "Cinematic video shot.",
            "negative_constraints": raw_shot.get("negative_constraints", []),
            "continuity_refs": raw_shot.get("continuity_refs", []),
            "required_events": raw_shot.get("required_events", []),
            "forbidden_events": raw_shot.get("forbidden_events", []),
            "generation_segments": raw_shot.get("generation_segments", []),
            "provenance": self._provenance(path, request_id),
        }

    @staticmethod
    def _build_sound(raw_shot: dict[str, Any]) -> list[str]:
        value = raw_shot.get("sound")
        if value is None:
            value = raw_shot.get("audio", [])
        if isinstance(value, str):
            return [value]
        return value if isinstance(value, list) else []

    def _build_state(self, value: Any, path: str, request_id: str) -> dict[str, Any]:
        source = value if isinstance(value, dict) else {}
        return {"description": source.get("description") or "State unspecified.", "character_states": source.get("character_states", {}), "prop_states": source.get("prop_states", {}), "environment_state": source.get("environment_state", ""), "continuity_notes": source.get("continuity_notes", []), "provenance": self._provenance(path, request_id)}

    def _build_character(self, value: Any, path: str, request_id: str, index: int) -> dict[str, Any]:
        source = value if isinstance(value, dict) else {}
        return {"character_id": source.get("character_id") or f"character-{index + 1:03d}", "provenance": self._provenance(path, request_id)}

    def _build_dialogue(self, value: Any, path: str, request_id: str) -> dict[str, Any]:
        source = value if isinstance(value, dict) else {}
        return {"speaker_id": source.get("speaker_id") or "speaker-generated-001", "text": source.get("text") or "", "emotion": source.get("emotion", ""), "delivery": source.get("delivery", ""), "provenance": self._provenance(path, request_id)}
