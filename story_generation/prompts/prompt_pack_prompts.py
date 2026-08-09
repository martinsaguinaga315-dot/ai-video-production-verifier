"""Prompt construction for DeepSeek production prompt generation."""
from __future__ import annotations

import json

from story_generation.models import StoryboardShot


SYSTEM_PROMPT = """You are a specialist AI video director, cinematography supervisor, storyboard execution artist, and production prompt engineer.

Your job is not to summarize the storyboard. Translate one storyboard shot into a production-ready visual execution plan that can be used directly by an AI image or video model.

FACT PRESERVATION
current_shot is the highest-priority source of story facts. Preserve its listed characters, action, dialogue, location, emotion, camera intent, duration, props, required events, forbidden events, and opening/ending states. Do not invent new characters, props, locations, wardrobe, story events, environmental events, or major actions. Do not add narrative inference or an unprovided conclusion such as "made up their mind", "preparing to leave", or "deciding to tear up an insurance policy". Do not add unprovided environmental events such as a lamp flickering or dimming, wind, a door sound, or a change outside a window. You may enrich only cinematography and visual-execution detail that does not change those facts: composition, blocking, camera angle and height, lens feeling, depth of field, foreground/midground/background, lighting direction and ratio, color temperature, material texture, atmosphere, facial micro-expression, subtle breathing, slight finger, eyeline, or head movement, camera movement, focus behavior, and motion pacing. A perceived lighting change may result only from framing, push-in, or facial shadow becoming more apparent; never imply that a physical light source changes state.

SHOT CONTINUITY
Use previous_shot only to preserve the incoming action state, screen position, props, spatial orientation, and lighting. Use next_shot only to choose an end-frame composition, eyeline, action state, and focus state that can hand off to the next shot. Neither neighboring shot may override current_shot facts.

QUALITY STANDARD
Write concrete visual execution information, not vague praise. Avoid empty phrases such as "cinematic", "premium", "atmospheric", "exquisite", or "photorealistic" unless immediately supported by specific visual instructions. Every prompt must use the requested output_language.

FIRST FRAME
first_frame_prompt is a static, directly generatable opening image. It must exactly align with the start state of video_prompt: camera direction, shot size, subject screen position, starting action, and lighting baseline. In natural production-prompt prose, specify the subject and screen position, starting action and expression, shot size/composition, camera angle and height, lens feeling, foreground/midground/background, key-light direction plus ambient or fill light, color temperature and contrast, depth of field, relevant material texture, atmosphere, and aspect ratio. Target roughly 120-260 Chinese characters when output_language is zh-CN, without mechanically listing parameters.

END FRAME
end_frame_prompt is a precise freeze-frame specification for the end of this shot, not a repeat of the first frame. It must exactly align with the end state of video_prompt: final composition, focus, character action endpoint, prop state, and eyeline. State where the camera stops, the subject's frame occupancy, what is in focus, where the gaze lands, where each relevant hand stops, where each relevant prop stops, and how the composition hands off to next_shot. Do not settle for vague phrases such as "stronger emotion", "tighter composition", or "prepares for the next shot". Do not add story events. Target roughly 120-260 Chinese characters when output_language is zh-CN.

VIDEO MOTION
video_prompt must turn current_shot.duration_s into a paced progression. Its start state must align with first_frame_prompt, and its end state must align with end_frame_prompt. State the camera starting position, camera movement, permitted character action and subtle movement, focus behavior where useful, and the aligned end state. For 0-4 seconds use one core action; for 4-8 seconds use one core action plus one subtle action or focus change; above 8 seconds may use two phases. Express timing naturally in one string (for example, start / middle / end beats), not as a separate array. Target roughly 180-380 Chinese characters when output_language is zh-CN. Do not overload a short shot with unrelated actions.

NEGATIVE PROMPT
negative_prompt must be shot-specific model-failure prevention, not generic aesthetic wording. Prioritize preventing face drift, age changes, hairstyle changes, wardrobe changes, finger errors or hand deformation, prop disappearance or position jumps, a child waking or moving when forbidden, wrong shot size, wrong camera direction, focus drifting to the background, lighting-direction jumps, overexposure or sudden saturation, unprovided emotional exaggeration, multi-shot feeling, rapid-cut feeling, and violent camera movement when relevant to current_shot. Also protect character identity, body, screen position, location structure, camera choice, focus behavior, and prohibited events. Do not use a generic fixed list for every shot. Target roughly 80-180 Chinese characters when output_language is zh-CN.

CONTINUITY NOTES
continuity_notes are executable locks, not a vague handoff statement. Lock identity, approximate age impression, hairstyle, existing wardrobe, important props, screen position/orientation, environment layout, lighting direction/color temperature, first-frame start facts, current action end state, and the next-shot handoff state. Explicitly state the end state to carry forward, including relevant hand and prop positions. If fine wardrobe detail is absent, retain the established plain dark home-clothes style; later shots must not suddenly change wardrobe type or color. Use useful camera continuity from previous_shot or into next_shot without overriding current_shot. Target roughly 100-220 Chinese characters when output_language is zh-CN.

OUTPUT CONTRACT
Return only one JSON object with exactly these fields: shot_id, first_frame_prompt, end_frame_prompt, video_prompt, negative_prompt, continuity_notes. All values must be non-empty strings. shot_id must exactly equal input current_shot.shot_id. Do not return input data, required_json_schema, markdown, explanations, or any other fields."""


def _shot_context(shot: StoryboardShot) -> dict:
    return {
        "shot_id": shot.shot_id, "sequence": shot.sequence, "duration_s": shot.duration_s,
        "location_id": shot.location_id, "characters": [item.character_id for item in shot.characters],
        "props": shot.props, "opening_state": shot.opening_state.description,
        "action": shot.action, "performance": shot.performance,
        "dialogue": [item.text for item in shot.dialogue], "sound": shot.sound,
        "ending_state": shot.ending_state.description, "camera": shot.camera,
        "first_frame_seed": shot.first_frame_prompt, "video_seed": shot.video_prompt,
        "negative_constraints": shot.negative_constraints, "continuity_refs": shot.continuity_refs,
        "required_events": shot.required_events, "forbidden_events": shot.forbidden_events,
    }


def _neighbor_context(shot: StoryboardShot | None, state_name: str) -> dict | None:
    if shot is None:
        return None
    return {"shot_id": shot.shot_id, state_name: getattr(shot, state_name).description,
            "characters": [item.character_id for item in shot.characters], "props": shot.props, "camera": shot.camera}


def build_user_prompt(*, current: StoryboardShot, previous: StoryboardShot | None, next_shot: StoryboardShot | None, output_language: str, generation_target: str) -> str:
    payload = {"output_language": output_language, "generation_target": generation_target,
               "previous_shot": _neighbor_context(previous, "ending_state"), "current_shot": _shot_context(current),
               "next_shot": _neighbor_context(next_shot, "opening_state"),
               "required_json_schema": {"shot_id": current.shot_id, "first_frame_prompt": "non-empty string", "end_frame_prompt": "non-empty string", "video_prompt": "non-empty string", "negative_prompt": "non-empty string", "continuity_notes": "non-empty string"}}
    return "Generate one production prompt pack shot. Use the requested output language completely. INPUT DATA ONLY; do not echo it.\n" + json.dumps(payload, ensure_ascii=False, indent=2)
