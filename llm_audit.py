from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from models import DirectorOutput, Issue, ProjectFacts

load_dotenv()


IDENTITY_CHANGE_PATTERNS = (
    r"不再是原来的",
    r"另一名完全不同",
    r"变成另一个人",
    r"变成另一名",
    r"换成另一名",
    r"替换为另一名",
    r"脸型.{0,12}(改变|变化|不同)",
    r"五官.{0,12}(改变|变化|不同)",
    r"身份.{0,12}(改变|变化|不同)",
    r"人物身份.{0,12}(改变|替换)",
)


def _field_value(value: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(field_name, default)
    return getattr(value, field_name, default)


def _normalize_text(value: Any) -> str:
    return re.sub(
        r"[\s，。、“”‘’：:；;！!？?…·\-—_（）()\[\]【】'\"/\\]",
        "",
        str(value or ""),
    ).lower()



SELF_NEGATING_CONCLUSION_PATTERNS = (
    re.compile(
        r"(?:综上|因此|所以|最终|结论(?:是|为)?|综合判断)"
        r"[^。！？!?\n]{0,24}"
        r"(?:无|不存在|没有|不构成|并非)"
        r"[^。！？!?\n]{0,28}"
        r"(?:冲突|违规|错误|问题)"
    ),
    re.compile(
        r"(?:无|不存在|没有|不构成|并非)"
        r"[^。！？!?\n]{0,20}"
        r"(?:跨镜头状态连续性冲突|连续性冲突|语义冲突|违规|错误)"
        r"\s*$"
    ),
    re.compile(
        r"(?:此条|该条|本条|本问题|该问题|此问题|该冲突|该错误|"
        r"this\s+issue|the\s+issue|issue)"
        r"[^。！？!?\n]{0,16}"
        r"(?:不成立|不存在|无效|无此问题|不应作为错误|不应视为错误|"
        r"不是错误|并非错误|不构成冲突|不属于连续性错误|"
        r"invalid|not\s+valid|no\s+conflict|not\s+an\s+error)"
        r"[\s。！？!?]*$",
        flags=re.IGNORECASE,
    ),
)

SELF_NEGATING_REASONABLE_MARKERS = (
    "因此合理",
    "所以合理",
    "属于合理",
    "状态合理",
    "位置合理",
    "并不矛盾",
    "不矛盾",
    "无矛盾",
    "没有矛盾",
)


def _message_tail(value: Any, max_length: int = 220) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return text[-max_length:]


def _is_self_negated_issue(issue: Issue) -> bool:
    """
    丢弃DeepSeek“标题报错、正文最终又认定无错”的异常输出。

    只检查message的最终结论，不根据suggestion做判断，避免把
    “修复后即可无冲突”误当成模型自我否定。
    """
    message = str(
        _field_value(issue, "message", "")
    ).strip()
    if not message:
        return False

    tail = _message_tail(message)

    if any(
        pattern.search(tail)
        for pattern in SELF_NEGATING_CONCLUSION_PATTERNS
    ):
        return True

    # 对结尾直接写“合理/不矛盾”的异常输出做保守过滤。
    normalized_tail = re.sub(r"\s+", "", tail)
    return any(
        normalized_tail.endswith(marker)
        or normalized_tail.endswith(marker + "。")
        for marker in SELF_NEGATING_REASONABLE_MARKERS
    )


CONTINUITY_RULE_IDS = {
    "SEMANTIC_STATE_CONTINUITY",
    "SEMANTIC_PROP_CONTINUITY",
    "SEMANTIC_IDENTITY_CONTINUITY",
}

CONTINUITY_CONFLICT_DENIAL_PATTERNS = (
    re.compile(r"(?:不|没有|无|并不)[^。！？!?\n]{0,10}冲突"),
    re.compile(r"(?:不|没有|无|并不)[^。！？!?\n]{0,10}矛盾"),
    re.compile(r"(?:保持|两者|状态|位置)[^。！？!?\n]{0,8}一致"),
    re.compile(r"与(?:前(?:一)?镜|上一镜|前镜|S\d{1,3})[^。！？!?\n]{0,20}一致", re.IGNORECASE),
    re.compile(r"未发生变化"),
)

CONTINUITY_CONFLICT_POSITIVE_MARKERS = (
    "不一致",
    "存在冲突",
    "发生冲突",
    "无依据变化",
    "跳变",
    "突变",
    "消失",
    "凭空出现",
    "无法解释",
    "身份漂移",
    "位置改变",
    "状态改变",
)

CONTINUITY_CONFLICT_POSITIVE_PATTERNS = (
    re.compile(r"(?:存在|发生|出现|明确|实际|完全)[^。！？!?\n]{0,16}(?:冲突|矛盾)"),
    re.compile(r"(?:状态|连续性|跨镜头)[^。！？!?\n]{0,8}冲突"),
    re.compile(r"(?<!不)(?<!无)矛盾"),
)


def _semantic_issue_explicitly_denies_continuity_conflict(
    issue: Issue,
) -> bool:
    """丢弃正文和证据已明确认定无连续性冲突的模型异常输出。"""
    rule_id = str(_field_value(issue, "rule_id", "")).upper()
    if rule_id not in CONTINUITY_RULE_IDS:
        return False

    blob = "\n".join(
        str(_field_value(issue, field_name, "")).strip()
        for field_name in ("message", "evidence")
        if str(_field_value(issue, field_name, "")).strip()
    )
    if not blob:
        return False

    normalized_blob = _normalize_text(blob)
    if any(
        _normalize_text(marker) in normalized_blob
        for marker in CONTINUITY_CONFLICT_POSITIVE_MARKERS
    ) or any(
        pattern.search(blob)
        for pattern in CONTINUITY_CONFLICT_POSITIVE_PATTERNS
    ):
        return False

    return any(
        pattern.search(blob)
        for pattern in CONTINUITY_CONFLICT_DENIAL_PATTERNS
    )


def _semantic_issue_is_omission_only_continuity_claim(
    issue: Issue,
) -> bool:
    """Drop continuity findings supported only by an omitted description.

    A continuity rule needs an explicit mutually exclusive state or change.
    Merely asking an author to repeat an otherwise compatible detail from the
    previous shot is a completeness suggestion, not a verification error.
    """
    rule_id = str(_field_value(issue, "rule_id", "")).upper()
    if rule_id not in CONTINUITY_RULE_IDS:
        return False

    blob = "\n".join(
        str(_field_value(issue, field_name, "")).strip()
        for field_name in ("message", "evidence")
        if str(_field_value(issue, field_name, "")).strip()
    )
    if not blob:
        return False

    normalized_blob = _normalize_text(blob)
    omission_markers = (
        "\u672a\u63d0\u53ca",
        "\u672a\u660e\u786e",
        "\u6ca1\u6709\u660e\u786e",
        "\u7f3a\u5c11\u63cf\u8ff0",
        "\u7f3a\u5c11\u8bf4\u660e",
        "\u672a\u8bf4\u660e",
        "\u6ca1\u6709\u8bf4\u660e",
        "\u672a\u5177\u4f53\u8bf4\u660e",
        "\u63cf\u8ff0\u4e0d\u5b8c\u6574",
        "\u5e94\u8fdb\u4e00\u6b65\u660e\u786e",
    )
    if not any(_normalize_text(marker) in normalized_blob for marker in omission_markers):
        return False

    explicit_change_markers = (
        "\u4e0d\u4e00\u81f4",
        "\u51b2\u7a81",
        "\u77db\u76fe",
        "\u8df3\u53d8",
        "\u7a81\u53d8",
        "\u6d88\u5931",
        "\u51ed\u7a7a\u51fa\u73b0",
        "\u4f4d\u7f6e\u6539\u53d8",
        "\u72b6\u6001\u6539\u53d8",
        "\u7269\u7406\u72b6\u6001\u53d8\u5316",
        "\u8eab\u4efd\u6f02\u79fb",
        "\u65e0\u4f9d\u636e\u79fb\u52a8",
        "\u65e0\u4f9d\u636e\u53d8\u5316",
        "\u524d\u540e\u4e0d\u540c",
    )
    if any(_normalize_text(marker) in normalized_blob for marker in explicit_change_markers):
        return False

    return True



EVENT_ORDER_RULE_IDS = {
    "SEMANTIC_EVENT_ORDER",
}

EVENT_ORDER_PATH_FIELDS = (
    "action_path",
    "video_prompt",
    "first_frame_prompt",
    "opening_state",
    "ending_state",
)


def _shot_by_id(
    collection: Any,
    shot_id: str,
) -> Any | None:
    for item in list(
        _field_value(collection, "shots", []) or []
    ):
        if str(
            _field_value(item, "shot_id", "")
        ).upper() == shot_id.upper():
            return item
    return None


def _event_order_target_field(issue: Issue) -> str:
    path = str(
        _field_value(issue, "path", "")
    ).lower()

    for field_name in EVENT_ORDER_PATH_FIELDS:
        if field_name.lower() in path:
            return field_name

    return ""


def _events_appear_in_required_order(
    required_events: list[str],
    field_text: Any,
) -> bool:
    """
    只验证facts固定事件之间的相对顺序。

    允许固定事件之前、之间或之后存在其他动作。
    其他动作是否过多，属于ACTION_FEASIBILITY等独立规则，
    不属于EVENT_ORDER。
    """
    normalized_text = _normalize_text(field_text)
    if not normalized_text:
        return False

    cursor = 0
    matched_count = 0

    for event in required_events:
        normalized_event = _normalize_text(event)
        if not normalized_event:
            continue

        position = normalized_text.find(
            normalized_event,
            cursor,
        )
        if position < 0:
            return False

        matched_count += 1
        cursor = position + len(normalized_event)

    return matched_count >= 2


def _is_false_event_order_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """
    丢弃DeepSeek把“固定事件前存在额外动作”
    误判为固定事件顺序错误的结果。

    只有当issue指向的字段中，facts.required_events全部存在，
    且它们的相对顺序正确时才过滤。缺失事件、真实逆序、
    指向其他字段的冲突均保留。
    """
    rule_id = str(
        _field_value(issue, "rule_id", "")
    ).upper()
    title = str(
        _field_value(issue, "title", "")
    )
    message = str(
        _field_value(issue, "message", "")
    )

    is_event_order_issue = (
        rule_id in EVENT_ORDER_RULE_IDS
        or "事件顺序" in title
        or (
            "顺序" in title
            and "required_events" in message
        )
    )
    if not is_event_order_issue:
        return False

    shot_id = _shot_id_from_issue(
        issue,
        output,
    )
    if not shot_id:
        return False

    facts_shot = _shot_by_id(
        facts,
        shot_id,
    )
    output_shot = _shot_by_id(
        output,
        shot_id,
    )
    if facts_shot is None or output_shot is None:
        return False

    required_events = [
        str(item)
        for item in (
            _field_value(
                facts_shot,
                "required_events",
                [],
            )
            or []
        )
        if str(item).strip()
    ]
    if len(required_events) < 2:
        return False

    target_field = _event_order_target_field(issue)
    if not target_field:
        return False

    target_text = _field_value(
        output_shot,
        target_field,
        "",
    )

    return _events_appear_in_required_order(
        required_events,
        target_text,
    )



def _shot_index_by_id(
    output: DirectorOutput,
    shot_id: str,
) -> int:
    shots = list(
        _field_value(output, "shots", []) or []
    )
    for index, shot in enumerate(shots):
        if str(
            _field_value(shot, "shot_id", "")
        ).upper() == shot_id.upper():
            return index
    return -1


def _is_false_same_shot_progression_issue(
    issue: Issue,
    output: DirectorOutput,
) -> bool:
    """
    过滤把同一镜头不同时间阶段误判成状态冲突的问题。

    时间层级：
    1. opening_state：镜头开始状态；
    2. first_frame_prompt：第一个画面瞬间；
    3. action_path / video_prompt：镜头开始后的动作发展。

    当上一镜ending_state与当前镜opening_state一致，且首帧也继承
    当前开场状态时，后续动作改变人物或道具状态属于合法时间推进。
    """
    rule_id = str(
        _field_value(issue, "rule_id", "")
    ).upper()
    if rule_id != "SEMANTIC_STATE_CONTINUITY":
        return False

    path = str(
        _field_value(issue, "path", "")
    ).lower()
    blob = "\n".join(
        [
            str(_field_value(issue, "message", "")),
            str(_field_value(issue, "evidence", "")),
        ]
    )
    normalized_blob = _normalize_text(blob)

    shot_id = _shot_id_from_issue(
        issue,
        output,
    )
    if not shot_id:
        return False

    current_index = _shot_index_by_id(
        output,
        shot_id,
    )
    if current_index <= 0:
        return False

    shots = list(
        _field_value(output, "shots", []) or []
    )
    previous_shot = shots[current_index - 1]
    current_shot = shots[current_index]

    previous_ending = _normalize_text(
        _field_value(
            previous_shot,
            "ending_state",
            "",
        )
    )
    current_opening = _normalize_text(
        _field_value(
            current_shot,
            "opening_state",
            "",
        )
    )

    if not previous_ending or not current_opening:
        return False

    if previous_ending != current_opening:
        return False

    # 分支一：opening_state -> action_path。
    opening_action_case = (
        "opening_state" in path
        and "actionpath" in normalized_blob
    )

    if opening_action_case:
        same_shot_change_markers = (
            "随后",
            "之后",
            "action_path",
            "镜头开始时即被改变",
            "opening_state未反映",
            "先收回",
            "站起",
            "坐下",
            "转身",
            "走到",
            "抬眼",
        )

        if any(
            _normalize_text(marker) in normalized_blob
            for marker in same_shot_change_markers
        ):
            return True

    # 分支二：first_frame_prompt -> video_prompt。
    # 首帧是t=0静态画面，video_prompt描述t>0的动作。
    mentions_frame_video = (
        (
            "first_frame_prompt" in path
            and "video_prompt" in path
        )
        or (
            "firstframeprompt" in normalized_blob
            and "videoprompt" in normalized_blob
        )
    )
    if not mentions_frame_video:
        return False

    first_frame = _normalize_text(
        _field_value(
            current_shot,
            "first_frame_prompt",
            "",
        )
    )
    if not first_frame:
        return False

    # 首帧必须实质继承opening_state，避免过滤真正的首帧错误。
    shared_initial_state = _longest_common_substring(
        current_opening,
        first_frame,
    )
    if len(shared_initial_state) < 8:
        return False

    # 只过滤模型自己已承认开场一致/不冲突，却又把后续动作判错的结果。
    acknowledged_initial_consistency = any(
        _normalize_text(marker) in normalized_blob
        for marker in (
            "opening_state与上一镜ending_state一致",
            "opening_state与s04ending_state一致",
            "状态一致",
            "不冲突因为动作发生在镜头开始后",
            "动作发生在镜头开始后",
            "首帧状态与开场状态一致",
        )
    )
    if not acknowledged_initial_consistency:
        return False

    phase_progression_markers = (
        "尚未移动",
        "尚未开始",
        "仍放在",
        "仍位于",
        "随后",
        "开始推",
        "先用",
        "立即开始",
        "后续动作",
        "video_prompt要求",
        "时间顺序",
    )

    return any(
        _normalize_text(marker) in normalized_blob
        for marker in phase_progression_markers
    )


def _is_false_same_shot_prop_progression_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """过滤把已连续继承的固定道具镜内可见移动误报为跨镜头冲突。"""
    if str(_field_value(issue, "rule_id", "")).upper() != (
        "SEMANTIC_PROP_CONTINUITY"
    ):
        return False

    path = str(_field_value(issue, "path", "")).lower()
    blob = _normalize_text(
        "\n".join(
            [
                str(_field_value(issue, "message", "")),
                str(_field_value(issue, "evidence", "")),
            ]
        )
    )
    if "actionpath" not in blob and "videoprompt" not in blob:
        return False

    aliases = _mentioned_prop_aliases(issue, facts, output)
    if not aliases:
        return False

    shot_id = _shot_id_from_issue(issue, output)
    current_index = _shot_index_by_id(output, shot_id)
    shots = list(_field_value(output, "shots", []) or [])
    if current_index <= 0 or current_index >= len(shots):
        return False

    previous_ending = _field_value(
        shots[current_index - 1], "ending_state", ""
    )
    current_opening = _field_value(
        shots[current_index], "opening_state", ""
    )
    first_frame = _field_value(
        shots[current_index], "first_frame_prompt", ""
    )
    prop_aliases = set(aliases)
    if not (
        _prop_boundary_state_is_equivalent(
            previous_ending,
            current_opening,
            prop_aliases,
        )
        and _prop_boundary_state_is_explicitly_inherited(
            current_opening,
            first_frame,
            prop_aliases,
        )
    ):
        return False

    action_text = _normalize_text(
        "\n".join(
            [
                str(_field_value(shots[current_index], "action_path", "")),
                str(_field_value(shots[current_index], "video_prompt", "")),
            ]
        )
    )
    movement_markers = (
        "移动", "推", "拿起", "放下", "放回", "递", "接过",
    )
    visible_process_markers = (
        "可见", "连续", "过程", "逐渐", "平稳",
    )
    return (
        any(alias in action_text for alias in aliases)
        and any(_normalize_text(marker) in action_text for marker in movement_markers)
        and any(
            _normalize_text(marker) in action_text
            for marker in visible_process_markers
        )
        and (
            "actionpath" in path
            or "videoprompt" in path
            or "actionpath" in blob
            or "videoprompt" in blob
        )
    )


def _is_false_continuity_issue_for_explicit_transition(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """Filter a continuity finding only when the output proves a legal in-shot transition."""
    if _issue_family(issue) not in {"state_continuity", "prop_continuity"}:
        return False

    current_index, phase, _, _ = _resolve_issue_target_shot(issue, output)
    shots = list(_field_value(output, "shots", []) or [])
    if current_index <= 0 or current_index >= len(shots):
        return False
    if phase not in {
        "opening_state", "first_frame_prompt", "action_path",
        "video_prompt", "ending_state",
    }:
        return False

    previous = shots[current_index - 1]
    current = shots[current_index]
    previous_ending = str(_field_value(previous, "ending_state", ""))
    opening = str(_field_value(current, "opening_state", ""))
    first_frame = str(_field_value(current, "first_frame_prompt", ""))
    ending = str(_field_value(current, "ending_state", ""))
    if not all((previous_ending.strip(), opening.strip(), first_frame.strip(), ending.strip())):
        return False

    # A genuine boundary or first-frame contradiction must never be hidden.
    boundary_issue = Issue(
        rule_id="SEMANTIC_STATE_CONTINUITY", severity="error", title="",
        message="", path=f"director_output.shots[{current_index}].opening_state",
        evidence="", suggestion="",
    )
    boundary = _analyze_boundary_conflicts(boundary_issue, facts, output)
    if boundary.get("scope") != "none":
        return False

    action_text = "\n".join(
        str(_field_value(current, field, ""))
        for field in ("action_path", "video_prompt", "performance")
    )
    normalized_action = _normalize_text(action_text)
    process_verbs = ("走", "移动", "推", "拉", "拿", "放", "递", "接", "按住", "松开", "转身", "站起", "坐下")
    temporal_markers = ("先", "随后", "然后", "之后", "接着", "镜头开场", "最后")
    visible_markers = ("可见", "连续", "完整", "平稳", "逐渐", "展示过程")
    if not (
        any(_normalize_text(marker) in normalized_action for marker in process_verbs)
        and any(_normalize_text(marker) in normalized_action for marker in temporal_markers)
        and any(_normalize_text(marker) in normalized_action for marker in visible_markers)
    ):
        return False

    aliases = _mentioned_prop_aliases(issue, facts, output)
    prop_supported = False
    if aliases:
        alias_set = set(aliases)
        prop_supported = (
            _prop_boundary_state_is_equivalent(previous_ending, opening, alias_set)
            and _prop_boundary_state_is_explicitly_inherited(opening, first_frame, alias_set)
            and any(alias in normalized_action for alias in alias_set)
            and any(alias in _normalize_text(ending) for alias in alias_set)
        )

    known_characters = _known_fact_and_output_character_ids(facts, output)
    human_supported = any(
        _normalize_text(character) in normalized_action
        and _normalize_text(character) in _normalize_text(ending)
        for character in known_characters
    ) and (
        len(_longest_common_substring(_normalize_text(previous_ending), _normalize_text(opening))) >= 8
        and len(_longest_common_substring(_normalize_text(opening), _normalize_text(first_frame))) >= 8
    )
    return prop_supported or human_supported


def _is_action_feasibility_duplicate_prop_issue(
    prop_issue: Issue,
    action_issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """判断镜内道具操作是否只是同一动作过载根因的重复包装。"""
    if (
        _issue_family(prop_issue) != "prop_continuity"
        or _issue_family(action_issue) != "action_feasibility"
    ):
        return False
    shot_id = _shot_id_from_issue(prop_issue, output)
    if not shot_id or shot_id != _shot_id_from_issue(action_issue, output):
        return False

    prop_path = _normalize_text(str(_field_value(prop_issue, "path", "")))
    prop_blob = _normalize_text(_prop_classification_blob(prop_issue))
    if not any(marker in prop_path or marker in prop_blob for marker in (
        "actionpath", "videoprompt", "generationsegments",
    )):
        return False

    current_index = _shot_index_by_id(output, shot_id)
    shots = list(_field_value(output, "shots", []) or [])
    if current_index <= 0 or current_index >= len(shots):
        return False
    aliases = _mentioned_prop_aliases(prop_issue, facts, output)
    if not aliases:
        return False

    previous_ending = _field_value(shots[current_index - 1], "ending_state", "")
    current_opening = _field_value(shots[current_index], "opening_state", "")
    prop_aliases = set(aliases)
    if (
        _extract_prop_state_clauses(previous_ending, prop_aliases)
        and _extract_prop_state_clauses(current_opening, prop_aliases)
        and not _prop_boundary_state_is_equivalent(
            previous_ending, current_opening, prop_aliases
        )
    ):
        return False

    action_text = _normalize_text("\n".join([
        str(_field_value(shots[current_index], "action_path", "")),
        str(_field_value(shots[current_index], "video_prompt", "")),
    ]))
    process_markers = ("拿起", "放下", "放回", "移动", "推", "递", "接过", "翻动", "走到")
    if not (
        any(alias in action_text for alias in aliases)
        and any(_normalize_text(marker) in action_text for marker in process_markers)
    ):
        return False

    action_blob = _normalize_text(_prop_classification_blob(action_issue))
    return any(
        _normalize_text(marker) in prop_blob
        and _normalize_text(marker) in action_blob
        for marker in process_markers
    )



ACTION_FEASIBILITY_UNCERTAINTY_MARKERS = (
    "可能无法",
    "可能不能",
    "实际可能",
    "或许无法",
    "未必能够",
    "时间紧张",
    "时间可能不够",
    "可能来不及",
    "存在无法完成的风险",
    "大概率无法",
)

ACTION_FEASIBILITY_CONCESSION_MARKERS = (
    "本身在",
    "本身可行",
    "单独可行",
    "可以完成",
    "可在",
    "在时长内可行",
    "推杯动作本身",
    "动作本身",
)

ACTION_FEASIBILITY_DEFINITE_MARKERS = (
    "至少需要",
    "保守估算完成时间",
    "明确超过镜头时长",
    "无法在镜头时长内完成",
    "必然无法完成",
    "总耗时超过",
)


def _is_speculative_action_feasibility_issue(
    issue: Issue,
    output: DirectorOutput,
) -> bool:
    """
    过滤只有“可能、时间紧张、存在风险”等推测措辞，
    但没有明确超时证据的动作可行性严重错误。

    严重错误必须证明动作最低完成时间明确超过镜头时长。
    如果模型同时承认动作本身可行，且确定性保守估算没有超时，
    则不应扣分。
    """
    rule_id = str(
        _field_value(issue, "rule_id", "")
    ).upper()
    if rule_id != "SEMANTIC_ACTION_FEASIBILITY":
        return False

    blob = "\n".join(
        [
            str(_field_value(issue, "title", "")),
            str(_field_value(issue, "message", "")),
            str(_field_value(issue, "evidence", "")),
        ]
    )
    normalized_blob = _normalize_text(blob)

    has_uncertainty = any(
        _normalize_text(marker) in normalized_blob
        for marker in ACTION_FEASIBILITY_UNCERTAINTY_MARKERS
    )
    if not has_uncertainty:
        return False

    # 有明确、可验证的超时下界时仍保留。
    has_definite_evidence = any(
        _normalize_text(marker) in normalized_blob
        for marker in ACTION_FEASIBILITY_DEFINITE_MARKERS
    )
    if has_definite_evidence:
        return False

    shot_id = _shot_id_from_issue(
        issue,
        output,
    )
    if not shot_id:
        return False

    shot = _shot_by_id(
        output,
        shot_id,
    )
    if shot is None:
        return False

    metrics = _action_feasibility_metrics(shot)

    # 极端动作过载由确定性预检保证，不能过滤。
    if _is_extreme_action_overload(metrics):
        return False

    duration = float(
        metrics.get("duration", 0.0)
    )
    estimated_min = float(
        metrics.get(
            "estimated_min_seconds",
            0.0,
        )
    )
    action_count = int(
        metrics.get("action_count", 0)
    )

    has_concession = any(
        _normalize_text(marker) in normalized_blob
        for marker in ACTION_FEASIBILITY_CONCESSION_MARKERS
    )

    # 保守估算未超过镜头时长，且模型只是表达可能性：
    # 不能作为严重错误。
    estimate_fits = (
        duration > 0
        and estimated_min <= duration
    )

    # 少量动作且没有明确超时证据，也不应因“时间紧张”扣分。
    modest_action_load = action_count <= 5

    return (
        estimate_fits
        and (
            has_concession
            or modest_action_load
        )
    )



def _is_unconfirmed_llm_action_feasibility_issue(
    issue: Issue,
    deterministic_action_shots: set[str],
    output: DirectorOutput,
) -> bool:
    """
    DeepSeek对动作节奏和最低耗时的判断容易随措辞波动。

    SEMANTIC_ACTION_FEASIBILITY作为严重错误时，必须由
    _action_feasibility_precheck确定性确认。未经确认的模型候选
    不参与扣分；已确认的模型候选也由后续去重逻辑删除，只保留
    确定性版本作为唯一根因。
    """
    if _issue_family(issue) != "action_feasibility":
        return False

    shot_id = _shot_id_from_issue(
        issue,
        output,
    )

    return (
        not shot_id
        or shot_id not in deterministic_action_shots
    )


def _issue_blob(issue: Issue) -> str:
    return "\n".join(
        [
            str(_field_value(issue, "rule_id", "")),
            str(_field_value(issue, "title", "")),
            str(_field_value(issue, "message", "")),
            str(_field_value(issue, "path", "")),
            str(_field_value(issue, "evidence", "")),
            str(_field_value(issue, "suggestion", "")),
        ]
    )


def _shot_id_from_issue(
    issue: Issue,
    output: DirectorOutput,
) -> str:
    """
    优先根据path定位问题所属镜头。

    连续性问题的message/evidence通常同时出现上一镜和当前镜头，
    例如“S04 ending_state vs S05 opening_state”。
    若先扫描正文，会错误抓到S04；实际问题路径shots[4]属于S05。
    """
    path = str(_field_value(issue, "path", ""))
    rule_id = str(_field_value(issue, "rule_id", "")).upper()
    if rule_id == "SEMANTIC_STATE_CONTINUITY":
        boundary_match = re.search(
            r"S\d{2,}\s*ending_state[\s\S]{0,240}?"
            r"S(\d{2,})\s*opening_state",
            "\n".join(
                [
                    str(_field_value(issue, "message", "")),
                    str(_field_value(issue, "evidence", "")),
                ]
            ),
            flags=re.IGNORECASE,
        )
        if boundary_match:
            return f"S{boundary_match.group(1)}".upper()

    indexed = re.search(
        r"(?:director_output\.)?shots\[(\d+)\]",
        path,
        flags=re.IGNORECASE,
    )
    if indexed:
        index = int(indexed.group(1))
        shots = list(_field_value(output, "shots", []) or [])
        if 0 <= index < len(shots):
            return str(
                _field_value(shots[index], "shot_id", "")
            ).upper()

    path_direct = re.search(
        r"shots[.\[]?(S\d{2,})",
        path,
        flags=re.IGNORECASE,
    )
    if path_direct:
        return path_direct.group(1).upper()

    direct_path = re.search(
        r"(S\d{2,})",
        path,
        flags=re.IGNORECASE,
    )
    if direct_path:
        return direct_path.group(1).upper()

    blob = _issue_blob(issue)
    direct_blob = re.search(
        r"(S\d{2,})",
        blob,
        flags=re.IGNORECASE,
    )
    if direct_blob:
        return direct_blob.group(1).upper()

    return ""


def _resolve_issue_target_shot(
    issue: Issue,
    output: DirectorOutput,
) -> tuple[int, str, str, str]:
    """从点式或数组路径解析当前镜头、阶段和规范路径。"""
    path = str(_field_value(issue, "path", ""))
    phase_match = re.search(
        r"(opening_state|first_frame_prompt|ending_state|action_path|video_prompt)",
        path,
        flags=re.IGNORECASE,
    )
    phase = phase_match.group(1).lower() if phase_match else "unknown"
    shots = list(_field_value(output, "shots", []) or [])
    direct = re.search(r"shots\.S(\d+)", path, flags=re.IGNORECASE)
    if direct:
        index = int(direct.group(1)) - 1
        if 0 <= index < len(shots):
            return index, phase, f"director_output.shots[{index}].{phase}", "dotted_path"
    indexed = re.search(r"shots\[(\d+)\]", path, flags=re.IGNORECASE)
    if indexed:
        index = int(indexed.group(1))
        if 0 <= index < len(shots):
            return index, phase, f"director_output.shots[{index}].{phase}", "array_path"
    shot_id = str(_field_value(issue, "shot_id", ""))
    index = _shot_index_by_id(output, shot_id)
    if index >= 0:
        return index, phase, f"director_output.shots[{index}].{phase}", "shot_id"
    return -1, phase, "", "unresolved"


def _issue_family(issue: Issue) -> str:
    rule_id = str(_field_value(issue, "rule_id", "")).upper()
    path = str(_field_value(issue, "path", "")).lower()
    blob = _issue_blob(issue)
    normalized = _normalize_text(blob)

    if rule_id == "UNKNOWN_CHARACTER":
        return "unknown_character"
    if rule_id == "UNKNOWN_PROP":
        return "unknown_prop"
    if rule_id == "SEMANTIC_STATE_CONTINUITY":
        return "state_continuity"
    if rule_id == "SEMANTIC_IDENTITY_CONTINUITY":
        return "identity"
    if rule_id == "SEMANTIC_PROP_CONTINUITY":
        return "prop_continuity"
    if rule_id == "SEMANTIC_ACTION_FEASIBILITY":
        return "action_feasibility"
    if rule_id == "SEMANTIC_EVENT_ORDER":
        return "event_order"
    if rule_id == "DIALOGUE_EXACT":
        return "dialogue"
    if rule_id == "FORBIDDEN_EVENT":
        return "forbidden_event"
    if rule_id in {
        "SEGMENT_MISSING",
        "SEGMENT_INCOMPLETE",
        "SEGMENT_DURATION_TOTAL",
        "SEGMENT_DURATION_INVALID",
        "SEGMENT_NAME_DUPLICATE",
    }:
        return "segment"
    if rule_id in {
        "TIME_GAP",
        "TIME_OVERLAP",
        "LOCKED_TIME",
        "DURATION_MISMATCH",
    }:
        return "timeline"
    if rule_id in {
        "MISSING_EVENT",
        "EVENT_WRONG_SHOT",
        "EVENT_TOO_EARLY",
    }:
        return "event"

    if (
        "dialogue" in path
        or "台词" in blob
        or "对话" in blob
        or "exact_dialogue" in blob
    ):
        return "dialogue"

    if (
        "generation_segments" in path
        or "generationsegments" in normalized
        or "生成分段" in blob
    ):
        return "segment"

    if (
        (
            "人物" in blob
            or "角色" in blob
            or "character" in normalized
        )
        and (
            "未定义" in blob
            or "新增角色" in blob
            or "增加人物" in blob
            or "擅自增加" in blob
            or "没有" in blob and "facts" in normalized
        )
    ):
        return "unknown_character"

    if (
        (
            "道具" in blob
            or "prop" in normalized
        )
        and (
            "未定义" in blob
            or "新增道具" in blob
            or "增加道具" in blob
            or "擅自增加" in blob
        )
    ):
        return "unknown_prop"

    referenced_shots = set(
        item.upper()
        for item in re.findall(
            r"S\d{2,}",
            blob,
            flags=re.IGNORECASE,
        )
    )
    if (
        "opening_state" in path
        or "ending_state" in path
        or "openingstate" in normalized
        or "endingstate" in normalized
    ) and (
        len(referenced_shots) >= 2
        or any(
            marker in blob
            for marker in (
                "上一镜",
                "前一镜",
                "结束时",
                "结尾状态",
                "延续",
                "突然",
                "状态矛盾",
                "状态冲突",
                "与S04结束",
            )
        )
    ):
        return "state_continuity"

    if (
        "negative_constraints" in blob
        or "forbidden_events" in blob
        or "禁用内容" in blob
        or "禁止" in blob
        or "不得" in blob
    ):
        return "forbidden_event"

    if (
        "身份连续性" in blob
        or "换人" in blob
        or "另一名完全不同" in blob
        or "五官" in blob and "改变" in blob
    ):
        return "identity"

    if (
        "固定事件" in blob
        or "required_events" in blob
        or "错误镜头" in blob
        or "事件遗漏" in blob
    ):
        return "event"

    return "other"


def _issue_fingerprint(issue: Issue, output: DirectorOutput) -> tuple[str, ...]:
    return (
        _issue_family(issue),
        _shot_id_from_issue(issue, output),
        _normalize_text(_field_value(issue, "path", "")),
        _normalize_text(_field_value(issue, "message", "")),
    )


def _has_content_overlap(first: Issue, second: Issue) -> bool:
    first_parts = re.split(
        r"[\n，。；;：:、]+",
        "\n".join(
            [
                str(_field_value(first, "message", "")),
                str(_field_value(first, "evidence", "")),
            ]
        ),
    )
    second_text = _normalize_text(_issue_blob(second))

    for part in first_parts:
        token = _normalize_text(part)
        if len(token) >= 4 and token in second_text:
            return True

    return False


def _is_duplicate_state_of_prop_continuity(
    state_issue: Issue,
    prop_issue: Issue,
    output: DirectorOutput,
    facts: ProjectFacts | None = None,
) -> bool:
    """
    专用道具连续性和通用状态连续性同时指向同一镜头、
    且具有实质证据重叠时，保留专用道具规则。

    不仅以镜头号判断：同镜头的独立人物状态冲突
    在没有证据重叠时仍应保留。
    """
    if (
        _issue_family(state_issue) != "state_continuity"
        or _issue_family(prop_issue) != "prop_continuity"
    ):
        return False

    state_shot = _shot_id_from_issue(state_issue, output)
    prop_shot = _shot_id_from_issue(prop_issue, output)
    if not state_shot or state_shot != prop_shot:
        return False

    if facts is not None:
        state_props = set(
            _mentioned_prop_aliases(
                state_issue,
                facts,
                output,
            ).values()
        )
        prop_props = set(
            _mentioned_prop_aliases(
                prop_issue,
                facts,
                output,
            ).values()
        )
        # A shared boundary is insufficient: the generic STATE must describe
        # the same registered prop before PROP priority can suppress it.
        if not state_props or not (state_props & prop_props):
            return False

    return _has_content_overlap(prop_issue, state_issue)


def _is_duplicate_prop_continuity(
    first: Issue,
    second: Issue,
    output: DirectorOutput,
) -> bool:
    """
    将同一镜头、同一证据根因的重复道具连续性报告合并为一条。

    不仅以镜头号判断，以免合并同镜头中不同道具的独立冲突。
    """
    if (
        _issue_family(first) != "prop_continuity"
        or _issue_family(second) != "prop_continuity"
    ):
        return False

    first_shot = _shot_id_from_issue(first, output)
    second_shot = _shot_id_from_issue(second, output)
    if not first_shot or first_shot != second_shot:
        return False

    return (
        _has_content_overlap(first, second)
        or _has_content_overlap(second, first)
    )


EVENT_ROOT_HARD_RULE_IDS = {
    "EVENT_TOO_EARLY",
    "FORBIDDEN_EVENT",
    "EVENT_WRONG_SHOT",
}

EVENT_ROOT_PROTECTED_SEMANTIC_RULE_IDS = {
    "SEMANTIC_STATE_CONTINUITY",
    "SEMANTIC_IDENTITY_CONTINUITY",
    "SEMANTIC_PROP_CONTINUITY",
}

ACTION_FRAGMENT_MARKERS = (
    "走到",
    "触碰",
    "按住",
    "拿起",
    "放下",
    "打开",
    "关闭",
    "离开",
    "回到",
    "站起",
    "坐下",
    "移动",
    "递给",
    "推向",
    "抬头",
    "低头",
    "看向",
    "转身",
    "伸手",
    "进入",
    "出现",
    "消失",
    "变成",
    "换成",
)


def _issue_event_text(issue: Issue) -> str:
    return "\n".join(
        [
            str(_field_value(issue, "message", "")),
            str(_field_value(issue, "evidence", "")),
            str(_field_value(issue, "suggestion", "")),
        ]
    )


def _known_character_ids(output: DirectorOutput) -> set[str]:
    result: set[str] = set()

    for shot in list(_field_value(output, "shots", []) or []):
        for character_id in list(
            _field_value(shot, "characters", []) or []
        ):
            value = _normalize_text(character_id)
            if value:
                result.add(value)

    return result


def _normalize_event_root_text(
    value: Any,
    output: DirectorOutput,
) -> str:
    normalized = _normalize_text(value)

    for character_id in _known_character_ids(output):
        normalized = normalized.replace(character_id, "")

    normalized = re.sub(r"s\d{2,}", "", normalized)
    return normalized


def _longest_common_substring(
    first: str,
    second: str,
) -> str:
    if not first or not second:
        return ""

    previous = [0] * (len(second) + 1)
    best_length = 0
    best_end = 0

    for first_index, first_char in enumerate(first, start=1):
        current = [0] * (len(second) + 1)

        for second_index, second_char in enumerate(
            second,
            start=1,
        ):
            if first_char != second_char:
                continue

            current[second_index] = (
                previous[second_index - 1] + 1
            )

            if current[second_index] > best_length:
                best_length = current[second_index]
                best_end = first_index

        previous = current

    return first[best_end - best_length : best_end]



def _is_state_boundary_derived_from_hard_event(
    semantic_issue: Issue,
    hard_issue: Issue,
    output: DirectorOutput,
) -> bool:
    """
    识别“硬规则事件错误 → 下一镜开场状态矛盾”的派生重复项。

    例：
    - EVENT_TOO_EARLY：S03中林夏提前走到餐桌旁。
    - SEMANTIC_STATE_CONTINUITY：因为该提前动作，S04 opening_state
      仍写林夏在门边，于是与S03 action_path矛盾。

    两条的根因和修复目标完全相同：删除S03提前动作。
    只保留硬规则EVENT_TOO_EARLY。
    """
    hard_rule_id = str(
        _field_value(hard_issue, "rule_id", "")
    ).upper()
    semantic_rule_id = str(
        _field_value(semantic_issue, "rule_id", "")
    ).upper()

    if hard_rule_id not in EVENT_ROOT_HARD_RULE_IDS:
        return False

    if semantic_rule_id != "SEMANTIC_STATE_CONTINUITY":
        return False

    hard_shot = _shot_id_from_issue(
        hard_issue,
        output,
    )
    semantic_blob = _normalize_text(
        _issue_blob(semantic_issue)
    )

    # 派生问题必须明确回指硬规则所在镜头或其action_path。
    if hard_shot:
        normalized_hard_shot = _normalize_text(hard_shot)
        references_hard_shot = (
            normalized_hard_shot in semantic_blob
            or _normalize_text(
                f"{hard_shot} action_path"
            ) in semantic_blob
        )
        if not references_hard_shot:
            return False

    semantic_text = _normalize_event_root_text(
        _issue_event_text(semantic_issue),
        output,
    )
    hard_text = _normalize_event_root_text(
        _issue_event_text(hard_issue),
        output,
    )
    shared_fragment = _longest_common_substring(
        semantic_text,
        hard_text,
    )

    if len(shared_fragment) >= 6:
        return True

    return (
        len(shared_fragment) >= 4
        and any(
            marker in shared_fragment
            for marker in ACTION_FRAGMENT_MARKERS
        )
    )


def _is_same_event_root_as_hard_issue(
    semantic_issue: Issue,
    hard_issue: Issue,
    output: DirectorOutput,
) -> bool:
    """
    过滤同一动作的语义派生重复项。

    例：
    - 硬规则：S03中的“走到餐桌旁”早于允许镜头。
    - 语义层：同一个“走到餐桌旁”在S03剩余时长内难以完成。

    两者的根因和修复目标相同，应只保留硬规则问题。
    """
    hard_rule_id = str(
        _field_value(hard_issue, "rule_id", "")
    ).upper()
    semantic_rule_id = str(
        _field_value(semantic_issue, "rule_id", "")
    ).upper()

    if hard_rule_id not in EVENT_ROOT_HARD_RULE_IDS:
        return False

    if (
        not semantic_rule_id.startswith("SEMANTIC_")
        or semantic_rule_id
        in EVENT_ROOT_PROTECTED_SEMANTIC_RULE_IDS
    ):
        return False

    semantic_shot = _shot_id_from_issue(
        semantic_issue,
        output,
    )
    hard_shot = _shot_id_from_issue(
        hard_issue,
        output,
    )

    if (
        semantic_shot
        and hard_shot
        and semantic_shot != hard_shot
    ):
        return False

    semantic_text = _normalize_event_root_text(
        _issue_event_text(semantic_issue),
        output,
    )
    hard_text = _normalize_event_root_text(
        _issue_event_text(hard_issue),
        output,
    )
    shared_fragment = _longest_common_substring(
        semantic_text,
        hard_text,
    )

    if len(shared_fragment) >= 6:
        return True

    return (
        len(shared_fragment) >= 4
        and any(
            marker in shared_fragment
            for marker in ACTION_FRAGMENT_MARKERS
        )
    )



UNKNOWN_ENTITY_HARD_RULE_IDS = {
    "UNKNOWN_CHARACTER",
    "UNKNOWN_PROP",
}

UNKNOWN_CHARACTER_GENERIC_MARKERS = (
    "第三名人物",
    "第三个人物",
    "额外人物",
    "新增人物",
    "未知人物",
    "未定义人物",
    "擅自增加人物",
)

UNKNOWN_PROP_GENERIC_MARKERS = (
    "额外道具",
    "新增道具",
    "未知道具",
    "未定义道具",
    "擅自增加道具",
)


def _quoted_entity_names(issue: Issue) -> set[str]:
    blob = "\n".join(
        [
            str(_field_value(issue, "title", "")),
            str(_field_value(issue, "message", "")),
            str(_field_value(issue, "evidence", "")),
        ]
    )

    result: set[str] = set()
    patterns = (
        r"“([^”]{1,40})”",
        r'"([^"]{1,40})"',
        r"'([^']{1,40})'",
        r"「([^」]{1,40})」",
    )

    for pattern in patterns:
        for matched in re.findall(pattern, blob):
            value = _normalize_text(matched)
            if value:
                result.add(value)

    return result


def _is_duplicate_of_unknown_entity_hard_issue(
    semantic_issue: Issue,
    hard_issue: Issue,
    output: DirectorOutput,
) -> bool:
    """
    当硬规则已经报告某个未知人物或未知道具时，删除语义层在
    action_path、video_prompt、negative_constraints等字段中
    对同一实体的重复展开。

    此判断不信任DeepSeek返回的rule_id。即使它误标为
    SEMANTIC_STATE_CONTINUITY，只要实体、镜头和根因一致，
    仍视为硬规则重复项。
    """
    hard_rule_id = str(
        _field_value(hard_issue, "rule_id", "")
    ).upper()

    if hard_rule_id not in UNKNOWN_ENTITY_HARD_RULE_IDS:
        return False

    semantic_shot = _shot_id_from_issue(
        semantic_issue,
        output,
    )
    hard_shot = _shot_id_from_issue(
        hard_issue,
        output,
    )

    if (
        semantic_shot
        and hard_shot
        and semantic_shot != hard_shot
    ):
        return False

    semantic_blob = _normalize_text(
        _issue_blob(semantic_issue)
    )
    entity_names = _quoted_entity_names(hard_issue)

    if any(
        entity_name in semantic_blob
        for entity_name in entity_names
    ):
        return True

    if hard_rule_id == "UNKNOWN_CHARACTER":
        return any(
            _normalize_text(marker) in semantic_blob
            for marker in UNKNOWN_CHARACTER_GENERIC_MARKERS
        )

    return any(
        _normalize_text(marker) in semantic_blob
        for marker in UNKNOWN_PROP_GENERIC_MARKERS
    )


def _is_duplicate_of_hard_issue(
    semantic_issue: Issue,
    hard_issue: Issue,
    output: DirectorOutput,
) -> bool:
    if _is_same_event_root_as_hard_issue(
        semantic_issue,
        hard_issue,
        output,
    ):
        return True

    if _is_state_boundary_derived_from_hard_event(
        semantic_issue,
        hard_issue,
        output,
    ):
        return True

    if _is_duplicate_of_unknown_entity_hard_issue(
        semantic_issue,
        hard_issue,
        output,
    ):
        return True

    semantic_family = _issue_family(semantic_issue)
    hard_family = _issue_family(hard_issue)

    if semantic_family != hard_family:
        return False

    semantic_shot = _shot_id_from_issue(semantic_issue, output)
    hard_shot = _shot_id_from_issue(hard_issue, output)

    if semantic_shot and hard_shot and semantic_shot != hard_shot:
        return False

    strong_families = {
        "unknown_character",
        "unknown_prop",
        "dialogue",
        "forbidden_event",
        "segment",
        "timeline",
    }

    if semantic_family in strong_families:
        return True

    return _has_content_overlap(semantic_issue, hard_issue)



def _is_duplicate_identity_of_hard_issue(
    semantic_issue: Issue,
    hard_issues: list[Issue],
    output: DirectorOutput,
) -> bool:
    """Drop identity findings fully covered by dialogue or unknown-entity rules."""
    if str(_field_value(semantic_issue, "rule_id", "")).upper() != "SEMANTIC_IDENTITY_CONTINUITY":
        return False
    blob = _prop_classification_blob(semantic_issue)
    if any(re.search(pattern, blob, flags=re.IGNORECASE) for pattern in IDENTITY_CHANGE_PATTERNS):
        return False
    path = str(_field_value(semantic_issue, "path", "")).lower()
    fields = ("dialogue", "dialogue_lines", "spoken_lines", "voiceover", "subtitle")
    dialogue_path = any(field in path for field in fields)
    dialogue_claim = any(
        _normalize_text(marker) in _normalize_text(blob)
        for marker in ("台词", "说话人", "speaker", "对话", "台词归属", "台词内容")
    )
    if not (dialogue_path or dialogue_claim):
        return False
    semantic_shot = _shot_id_from_issue(semantic_issue, output)
    for hard_issue in hard_issues:
        hard_rule = str(_field_value(hard_issue, "rule_id", "")).upper()
        if hard_rule not in {"DIALOGUE_EXACT", "DIALOGUE_SPEAKER", "DIALOGUE_WRONG_SHOT", "UNKNOWN_CHARACTER"}:
            continue
        hard_shot = _shot_id_from_issue(hard_issue, output)
        if semantic_shot and hard_shot and semantic_shot != hard_shot:
            continue
        if hard_rule == "UNKNOWN_CHARACTER":
            if _is_duplicate_of_unknown_entity_hard_issue(semantic_issue, hard_issue, output):
                return True
            continue
        hard_path = str(_field_value(hard_issue, "path", "")).lower()
        if dialogue_path and any(field in hard_path for field in fields):
            return True
        if dialogue_claim and _has_content_overlap(semantic_issue, hard_issue):
            return True
    return False


def _has_explicit_event_order_reversal(issue: Issue) -> bool:
    """Require a concrete two-event reversal rather than a speaker attribution error."""
    text = _normalize_text(_prop_classification_blob(issue))
    order_markers = ("应先于", "应在", "之前", "之后", "先", "后", "反转", "逆序")
    return (
        any(marker in text for marker in ("反转", "逆序", "应先于"))
        or (
            "先" in text
            and "后" in text
            and any(marker in text for marker in ("应", "但", "实际"))
        )
    )


def _validate_event_order_issue_family(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> Issue | None:
    """Reject event-order labels that contain no real multi-event ordering evidence."""
    if str(_field_value(issue, "rule_id", "")).upper() != "SEMANTIC_EVENT_ORDER":
        return issue
    path = str(_field_value(issue, "path", "")).lower()
    dialogue_field = any(field in path for field in ("dialogue", "dialogue_lines", "spoken_lines", "voiceover", "subtitle"))
    blob = _normalize_text(_prop_classification_blob(issue))
    attribution_only = any(marker in blob for marker in ("说话人", "speaker", "台词归属", "错误分配", "由错误人物说出"))
    if (dialogue_field or attribution_only) and not _has_explicit_event_order_reversal(issue):
        return None
    if _is_false_event_order_issue(issue, facts, output):
        return None
    return issue


def _validate_identity_issue_family(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> Issue | None:
    """Require identity findings to carry an actual identity-anchor contradiction."""
    if str(_field_value(issue, "rule_id", "")).upper() != "SEMANTIC_IDENTITY_CONTINUITY":
        return issue
    blob = _prop_classification_blob(issue)
    if any(re.search(pattern, blob, flags=re.IGNORECASE) for pattern in IDENTITY_CHANGE_PATTERNS):
        return issue
    boundary = _analyze_boundary_conflicts(issue, facts, output)
    if boundary.get("phase") == "opening_state" and boundary.get("scope") in {"human", "mixed"}:
        return _human_boundary_state_issue(issue, facts, output)
    # Dialogue attribution, ordinary pose/position/contact changes, an unknown
    # person, and a generic "inconsistent person" claim do not prove identity.
    return None


def _is_semantic_issue_covered_by_hard_rules(
    semantic_issue: Issue,
    hard_issues: list[Issue],
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """Filter only semantic restatements of an already reported hard-rule root cause."""
    if any(_is_duplicate_of_hard_issue(semantic_issue, item, output) for item in hard_issues):
        return True
    if (
        str(_field_value(semantic_issue, "rule_id", "")).upper()
        == "SEMANTIC_IDENTITY_CONTINUITY"
        and any(
            re.search(pattern, _prop_classification_blob(semantic_issue), flags=re.IGNORECASE)
            for pattern in IDENTITY_CHANGE_PATTERNS
        )
    ):
        return False
    path = str(_field_value(semantic_issue, "path", "")).lower()
    dialogue_field = any(field in path for field in ("dialogue", "dialogue_lines", "spoken_lines", "voiceover", "subtitle"))
    if not dialogue_field:
        return False
    if str(_field_value(semantic_issue, "rule_id", "")).upper() == "SEMANTIC_EVENT_ORDER" and _has_explicit_event_order_reversal(semantic_issue):
        return False
    semantic_shot = _shot_id_from_issue(semantic_issue, output)
    for hard_issue in hard_issues:
        hard_rule = str(_field_value(hard_issue, "rule_id", "")).upper()
        if hard_rule not in {"DIALOGUE_EXACT", "DIALOGUE_SPEAKER", "DIALOGUE_WRONG_SHOT", "UNKNOWN_CHARACTER"}:
            continue
        hard_shot = _shot_id_from_issue(hard_issue, output)
        if semantic_shot and hard_shot and semantic_shot != hard_shot:
            continue
        if hard_rule == "UNKNOWN_CHARACTER":
            if _is_duplicate_of_unknown_entity_hard_issue(semantic_issue, hard_issue, output):
                return True
        else:
            return True
    return False


STATE_REFERENCE_ONLY_MARKERS = (
    "与上述相同",
    "同上述",
    "同上",
    "不再重复列出",
    "不再重复说明",
    "参见上述",
    "如上所述",
    "同前述冲突",
    "同opening_state的冲突",
    "同first_frame_prompt的冲突",
)


def _is_reference_only_state_issue(issue: Issue) -> bool:
    """
    识别只引用另一条主问题、没有独立根因的附属条目。

    示例：
    “generation_segments中存在与上述相同的状态冲突，
    不再重复列出。”
    """
    message = str(
        _field_value(issue, "message", "")
    )
    evidence = str(
        _field_value(issue, "evidence", "")
    )
    blob = message + "\n" + evidence

    return any(
        marker in blob
        for marker in STATE_REFERENCE_ONLY_MARKERS
    )


def _state_issue_priority(
    issue: Issue,
) -> tuple[int, int]:
    """
    合并时优先保留真正描述镜头边界冲突的主问题。
    """
    path = str(
        _field_value(issue, "path", "")
    ).lower()
    message = str(
        _field_value(issue, "message", "")
    )

    if "opening_state" in path:
        path_priority = 0
    elif "ending_state" in path:
        path_priority = 1
    elif "first_frame_prompt" in path:
        path_priority = 2
    elif "video_prompt" in path:
        path_priority = 3
    elif "generation_segments" in path:
        path_priority = 5
    else:
        path_priority = 4

    # 更长、更具体的正文优先。
    return (
        path_priority,
        -len(message),
    )


def _merge_state_continuity_group(
    issues: list[Issue],
    output: DirectorOutput,
) -> Issue:
    ordered_issues = sorted(
        issues,
        key=_state_issue_priority,
    )

    detailed_issues = [
        item
        for item in ordered_issues
        if not _is_reference_only_state_issue(item)
    ]
    if detailed_issues:
        ordered_issues = detailed_issues

    first = ordered_issues[0]
    shot_id = _shot_id_from_issue(first, output)
    path = str(_field_value(first, "path", ""))

    if (
        len(ordered_issues) == 1
        and "first_frame_prompt" in path.lower()
        and "首帧状态" in str(
            _field_value(first, "title", "")
        )
    ):
        return first

    current_index = _shot_index_by_id(output, shot_id)
    if current_index >= 0:
        path = f"director_output.shots[{current_index}].opening_state"

    messages: list[str] = []
    evidences: list[str] = []

    for item in ordered_issues:
        message = str(_field_value(item, "message", "")).strip()
        evidence = str(_field_value(item, "evidence", "")).strip()

        if message and message not in messages:
            messages.append(message)
        if evidence and evidence not in evidences:
            evidences.append(evidence)

    if len(messages) == 1:
        merged_message = messages[0]
    else:
        numbered = "\n".join(
            f"{index}. {message}"
            for index, message in enumerate(messages, start=1)
        )
        merged_message = (
            f"{shot_id or '当前镜头'}的opening_state与上一镜"
            f"ending_state存在{len(messages)}处相互关联的状态冲突：\n"
            f"{numbered}"
        )

    return Issue(
        rule_id="SEMANTIC_STATE_CONTINUITY",
        severity="error",
        title="跨镜头状态连续性冲突",
        message=merged_message,
        path=path,
        evidence="\n".join(evidences),
        suggestion=(
            "让当前镜头的opening_state直接继承上一镜的ending_state。"
            "只有facts明确规定状态变化时，才允许改变人物位置、"
            "动作姿态、道具状态或画面中的持续性元素。"
        ),
    )



STATE_BEARING_PATH_FIELDS = (
    "opening_state",
    "ending_state",
    "first_frame_prompt",
    "video_prompt",
    "action_path",
    "generation_segments",
)

STATE_CONFLICT_MARKERS = (
    "固定事实冲突",
    "required_events",
    "开场状态",
    "结束状态",
    "结尾状态",
    "上一镜",
    "前一镜",
    "延续",
    "状态矛盾",
    "状态冲突",
    "位置冲突",
    "姿态冲突",
    "与固定事实不符",
    "违反了固定事实",
)


def _is_state_derived_semantic_issue(
    issue: Issue,
) -> bool:
    """
    判断语义问题是否属于镜头状态冲突的字段级派生报告。

    当同一镜头已经存在跨镜头连续性主问题时，
    opening_state、first_frame_prompt、video_prompt、action_path
    中的SEMANTIC_X状态问题通常只是同一根因的重复展开。
    """
    rule_id = str(
        _field_value(issue, "rule_id", "")
    ).upper()

    protected_rule_ids = {
        "UNKNOWN_CHARACTER",
        "UNKNOWN_PROP",
        "DIALOGUE_EXACT",
        "FORBIDDEN_EVENT",
        "SEGMENT_MISSING",
        "SEGMENT_INCOMPLETE",
        "SEGMENT_DURATION_TOTAL",
        "SEGMENT_DURATION_INVALID",
        "SEGMENT_NAME_DUPLICATE",
        "TIME_GAP",
        "TIME_OVERLAP",
        "LOCKED_TIME",
        "DURATION_MISMATCH",
        "SEMANTIC_IDENTITY_CONTINUITY",
        "SEMANTIC_EVENT_ORDER",
        "SEMANTIC_ACTION_FEASIBILITY",
    }
    if rule_id in protected_rule_ids:
        return False

    path = str(_field_value(issue, "path", "")).lower()
    blob = _issue_blob(issue)
    normalized_blob = _normalize_text(blob)

    has_state_path = any(
        field_name in path
        for field_name in STATE_BEARING_PATH_FIELDS
    )
    if not has_state_path:
        return False

    # 只保护真正独立的问题。
    # “说出台词”只是动作描述中的普通措辞，不能因此把状态问题
    # 错误归类为台词问题。
    strong_independent_markers = (
        "说话人错误",
        "台词内容错误",
        "台词或所属镜头错误",
        "台词顺序错误",
        "擅加台词",
        "新增台词",
        "漏掉台词",
        "缺少台词",
        "speaker mismatch",
        "exact_dialogue",
        "未知人物",
        "新增人物",
        "第三名人物",
        "未知道具",
        "新增道具",
        "身份连续性",
        "换人",
        "另一张脸",
        "generation_segments",
        "生成分段",
        "时间轴",
        "时长错误",
        "时间空档",
        "时间重叠",
    )
    if any(
        _normalize_text(marker) in normalized_blob
        for marker in strong_independent_markers
    ):
        return False

    # 路径本身明确指向dialogue时，仍视为独立台词问题。
    if "dialogue" in path:
        return False

    state_markers = STATE_CONFLICT_MARKERS + (
        "facts",
        "固定事实",
        "人物位置",
        "站位",
        "坐着",
        "站起",
        "门边",
        "对面",
        "左手",
        "右手",
        "信封位置",
        "未提及",
        "未明确",
        "整体状态",
    )

    return (
        rule_id.startswith("SEMANTIC_")
        and any(
            _normalize_text(marker) in normalized_blob
            for marker in state_markers
        )
    )


def _continuity_anchor_shots(
    issues: list[Issue],
    output: DirectorOutput,
) -> set[str]:
    return {
        _shot_id_from_issue(issue, output)
        for issue in issues
        if _issue_family(issue) == "state_continuity"
        and _shot_id_from_issue(issue, output)
    }


def _collapse_state_derived_siblings(
    issues: list[Issue],
    output: DirectorOutput,
    facts: ProjectFacts | None = None,
) -> list[Issue]:
    """
    当同一镜头已有跨镜头连续性主问题时，删除同一根因派生出的
    字段级固定事实冲突，保留一个聚合后的连续性问题。

    不吸收台词、身份、禁用事件、未知实体、分段和时间轴等独立问题。
    """
    state_anchors = [
        issue for issue in issues
        if _issue_family(issue) == "state_continuity"
    ]
    anchor_shots = _continuity_anchor_shots(issues, output)
    if not anchor_shots:
        return issues

    result: list[Issue] = []

    for issue in issues:
        shot_id = _shot_id_from_issue(issue, output)
        family = _issue_family(issue)

        if family == "state_continuity":
            result.append(issue)
            continue

        if family == "prop_continuity" and facts is not None:
            # A shared current shot is not a shared cause.  Preserve a real prop
            # contradiction when no STATE anchor describes the same registered
            # prop with overlapping evidence; mixed-boundary conversion has
            # already converted inseparable PROP facets to STATE upstream.
            if not any(
                _is_duplicate_state_of_prop_continuity(
                    state_issue, issue, output, facts
                )
                for state_issue in state_anchors
            ):
                # A mixed boundary can be reported as a detailed PROP plus a
                # terse STATE whose wording only names the human facet.  The
                # shared relation is established from the output boundary, not
                # by requiring the STATE prose to repeat the prop name.
                if _is_inseparable_mixed_boundary_prop_issue(
                    issue, facts, output
                ) and any(
                    _same_opening_boundary(state_issue, issue, output)
                    for state_issue in state_anchors
                ):
                    continue
                result.append(issue)
                continue

        if (
            shot_id in anchor_shots
            and _is_state_derived_semantic_issue(issue)
        ):
            continue

        result.append(issue)

    return result

def _filter_and_group_semantic_issues(
    hard_issues: list[Issue],
    semantic_issues: list[Issue],
    output: DirectorOutput,
    facts: ProjectFacts | None = None,
) -> list[Issue]:
    filtered: list[Issue] = []
    seen: set[tuple[str, ...]] = set()

    for semantic_issue in semantic_issues:
        if any(
            _is_duplicate_of_hard_issue(
                semantic_issue,
                hard_issue,
                output,
            )
            for hard_issue in hard_issues
        ):
            continue

        if facts is not None and any(
            _is_action_feasibility_duplicate_prop_issue(
                semantic_issue,
                action_issue,
                facts,
                output,
            )
            for action_issue in semantic_issues
        ):
            continue

        if (
            _issue_family(semantic_issue) == "prop_continuity"
            and any(
                _is_duplicate_prop_continuity(
                    semantic_issue,
                    existing_issue,
                    output,
                )
                for existing_issue in filtered
            )
        ):
            continue

        fingerprint = _issue_fingerprint(semantic_issue, output)
        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        filtered.append(semantic_issue)

    prop_continuity_issues = [
        item
        for item in filtered
        if _issue_family(item) == "prop_continuity"
    ]

    continuity_groups: dict[tuple[str, str], list[Issue]] = {}
    passthrough: list[Issue] = []

    for item in filtered:
        family = _issue_family(item)
        if (
            family == "state_continuity"
            and any(
                _is_duplicate_state_of_prop_continuity(
                    item,
                    prop_issue,
                    output,
                    facts,
                )
                for prop_issue in prop_continuity_issues
            )
        ):
            continue

        if family != "state_continuity":
            passthrough.append(item)
            continue

        key = (
            _shot_id_from_issue(item, output),
            "shot_boundary",
        )
        continuity_groups.setdefault(key, []).append(item)

    for group in continuity_groups.values():
        passthrough.append(
            _merge_state_continuity_group(group, output)
        )

    return _collapse_state_derived_siblings(
        passthrough,
        output,
        facts,
    )



PROP_CONTINUITY_MARKERS = (
    "无依据消失",
    "突然消失",
    "凭空消失",
    "已经消失",
    "不见了",
    "道具消失",
    "无依据出现",
    "突然出现",
    "凭空出现",
    "位置跳变",
    "道具位置",
    "道具状态",
    "与facts冲突",
    "与固定事实冲突",
    "始终在",
    "保持在",
    "未规定消失",
    "没有拿走",
    "没有移动",
    "没有消失事件",
)


def _known_prop_ids(
    facts: ProjectFacts,
    output: DirectorOutput,
) -> set[str]:
    result: set[str] = set()

    for prop in list(_field_value(facts, "props", []) or []):
        prop_id = str(
            _field_value(prop, "prop_id", "")
        ).strip()
        if prop_id:
            result.add(prop_id)

        prop_name = str(
            _field_value(prop, "name", "")
        ).strip()
        if prop_name:
            result.add(prop_name)

    for prop in list(_field_value(output, "props", []) or []):
        prop_id = str(
            _field_value(prop, "prop_id", "")
        ).strip()
        if prop_id:
            result.add(prop_id)

        prop_name = str(
            _field_value(prop, "name", "")
        ).strip()
        if prop_name:
            result.add(prop_name)

    return result


def _prop_classification_blob(issue: Issue) -> str:
    """
    道具规则分类只看问题本身的标题、正文、路径和证据。

    suggestion通常包含通用模板：
    “人物位置、动作姿态、道具状态或画面元素……”
    不能因为修复建议提到“道具状态”，就把人物位置冲突误分类。
    """
    return "\n".join(
        [
            str(_field_value(issue, "title", "")),
            str(_field_value(issue, "message", "")),
            str(_field_value(issue, "path", "")),
            str(_field_value(issue, "evidence", "")),
        ]
    )



PROP_OBJECT_SUFFIXES = (
    "金属打火机",
    "牛皮纸信封",
    "笔记本",
    "打火机",
    "水杯",
    "信封",
    "书本",
    "手枪",
    "手机",
    "钥匙",
    "照片",
    "文件",
    "纸条",
    "信件",
    "杯子",
    "长剑",
    "短剑",
    "钢笔",
    "铅笔",
    "笔",
)

PROP_FOCUSED_CHANGE_MARKERS = (
    "无依据",
    "无过渡",
    "突然",
    "凭空",
    "位置",
    "移动",
    "出现在",
    "停在",
    "不再位于",
    "消失",
    "出现",
    "破损",
    "裂纹",
    "缺损",
    "完整无损",
    "状态跳变",
    "位置跳变",
    "没有人物移动",
    "没有移动过程",
)

HUMAN_FOCUSED_CHANGE_MARKERS = (
    "站在",
    "坐在",
    "走到",
    "走向",
    "门边",
    "餐桌旁",
    "教室门口",
    "人物位置",
    "位置瞬移",
    "无依据瞬移",
    "服装",
    "身份",
    "外观",
    "姿态",
    "发型",
    "年龄",
    "面部",
    "按住",
    "按在",
    "离开",
    "握住",
    "松开",
    "触碰",
    "拿着",
    "持有",
)


def _prop_aliases(prop_id: str) -> set[str]:
    """
    为固定道具生成稳定别名。

    例如：
    “未拆封的牛皮纸信封” -> “牛皮纸信封”“信封”
    避免上一镜只写简称“信封”时无法识别为同一道具。
    """
    raw = str(prop_id).strip()
    if not raw:
        return set()

    normalized = _normalize_text(raw)
    result = {normalized}

    for suffix in PROP_OBJECT_SUFFIXES:
        normalized_suffix = _normalize_text(suffix)
        if (
            normalized_suffix
            and normalized.endswith(normalized_suffix)
        ):
            result.add(normalized_suffix)

    return {
        item
        for item in result
        if item
    }


def _known_prop_alias_map(
    facts: ProjectFacts,
    output: DirectorOutput,
) -> dict[str, str]:
    result: dict[str, str] = {}

    for prop_id in _known_prop_ids(facts, output):
        for alias in _prop_aliases(prop_id):
            # 同一别名冲突时保留更具体、更长的正式名称。
            current = result.get(alias, "")
            if len(prop_id) > len(current):
                result[alias] = prop_id

    return result


def _known_fact_and_output_character_ids(
    facts: ProjectFacts,
    output: DirectorOutput,
) -> set[str]:
    result: set[str] = set()

    for character in list(
        _field_value(facts, "characters", []) or []
    ):
        character_id = str(
            _field_value(
                character,
                "character_id",
                "",
            )
        ).strip()
        if character_id:
            result.add(character_id)

    for character in list(
        _field_value(output, "characters", []) or []
    ):
        character_id = str(
            _field_value(
                character,
                "character_id",
                "",
            )
        ).strip()
        if character_id:
            result.add(character_id)

    return result


def _issue_clauses(issue: Issue) -> list[str]:
    return [
        item.strip()
        for item in re.split(
            r"[。；;\n]+",
            _prop_classification_blob(issue),
        )
        if item.strip()
    ]


def _mentioned_prop_aliases(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> dict[str, str]:
    normalized_blob = _normalize_text(
        _prop_classification_blob(issue)
    )
    alias_map = _known_prop_alias_map(
        facts,
        output,
    )
    return {
        alias: canonical
        for alias, canonical in alias_map.items()
        if alias in normalized_blob
    }


def _extract_prop_state_clauses(
    state_text: Any,
    prop_aliases: set[str],
) -> list[str]:
    """提取状态文本中只描述指定固定道具的片段。"""
    return [
        _normalize_text(fragment)
        for fragment in re.split(
            r"[。；;\n，,]+",
            str(state_text or ""),
        )
        if (
            _normalize_text(fragment)
            and any(
                alias in _normalize_text(fragment)
                for alias in prop_aliases
            )
        )
    ]


def _prop_boundary_state_is_equivalent(
    previous_state: Any,
    current_state: Any,
    prop_aliases: set[str],
) -> bool:
    """比较同一道具的显式状态；省略或补充兼容细节不视为冲突。"""
    previous_clauses = _extract_prop_state_clauses(
        previous_state,
        prop_aliases,
    )
    current_clauses = _extract_prop_state_clauses(
        current_state,
        prop_aliases,
    )
    if not previous_clauses or not current_clauses:
        return False

    for previous_clause in previous_clauses:
        for current_clause in current_clauses:
            if (
                previous_clause == current_clause
                or previous_clause in current_clause
                or current_clause in previous_clause
            ):
                return True

    previous_blob = "\n".join(previous_clauses)
    current_blob = "\n".join(current_clauses)

    # 只有两侧明确给出互斥状态时才认定不连续。
    opposite_pairs = (
        ("未拆封", "已拆封"),
        ("未打开", "已打开"),
        ("关闭", "打开"),
        ("完整无损", "破损"),
        ("完整无损", "缺损"),
        ("完整无损", "裂口"),
        ("完整", "破损"),
        ("完整", "缺损"),
        ("完整", "裂口"),
        ("无裂纹", "裂纹"),
        ("干燥", "湿透"),
        ("未触碰", "已触碰"),
    )
    for left, right in opposite_pairs:
        left_norm = _normalize_text(left)
        right_norm = _normalize_text(right)
        if (
            left_norm in previous_blob
            and right_norm in current_blob
        ) or (
            right_norm in previous_blob
            and left_norm in current_blob
        ):
            return False

    location_anchors = (
        "桌面左侧", "桌面右侧", "桌面中央", "桌边",
        "窗台", "地面", "手中", "左手前方", "右手前方",
        "左侧", "右侧", "前方", "后方",
    )
    previous_locations = {
        _normalize_text(anchor)
        for anchor in location_anchors
        if _normalize_text(anchor) in previous_blob
    }
    current_locations = {
        _normalize_text(anchor)
        for anchor in location_anchors
        if _normalize_text(anchor) in current_blob
    }
    if (
        previous_locations
        and current_locations
        and previous_locations.isdisjoint(current_locations)
    ):
        return False

    compatible_state_anchors = (
        "未拆封", "已拆封", "未打开", "已打开", "关闭", "打开",
        "完整无损", "完整", "破损", "无裂纹", "裂纹",
        "干燥", "湿透", "未触碰",
    )
    previous_states = {
        _normalize_text(anchor)
        for anchor in compatible_state_anchors
        if _normalize_text(anchor) in previous_blob
    }
    current_states = {
        _normalize_text(anchor)
        for anchor in compatible_state_anchors
        if _normalize_text(anchor) in current_blob
    }

    # 共享明确物理状态，或下一镜明确写“位置/状态不变”，说明两侧兼容。
    if previous_states & current_states:
        return True
    if any(
        _normalize_text(marker) in current_blob
        for marker in ("位置不变", "状态不变", "保持不变", "仍", "依然")
    ):
        return True

    return False


def _prop_boundary_state_is_explicitly_inherited(
    previous_state: Any,
    current_state: Any,
    prop_aliases: set[str],
) -> bool:
    """识别首帧以不同语序明确复述同一道具初始状态的情况。"""
    if _prop_boundary_state_is_equivalent(
        previous_state, current_state, prop_aliases
    ):
        return True
    previous_clauses = _extract_prop_state_clauses(
        previous_state, prop_aliases
    )
    current_clauses = _extract_prop_state_clauses(
        current_state, prop_aliases
    )
    anchors = (
        "桌面左侧", "桌面右侧", "桌面中央", "窗台", "地面",
        "手中", "前方", "后方", "完整无损", "未拆封", "已拆封",
        "裂纹", "破损", "缺损", "缺口",
    )
    persistence_markers = ("仍", "保持", "尚未", "依然")
    for previous_clause in previous_clauses:
        previous_anchors = {
            _normalize_text(anchor)
            for anchor in anchors
            if _normalize_text(anchor) in previous_clause
        }
        if not previous_anchors:
            continue
        for current_clause in current_clauses:
            if not any(
                _normalize_text(marker) in current_clause
                for marker in persistence_markers
            ):
                continue
            if previous_anchors <= {
                _normalize_text(anchor)
                for anchor in anchors
                if _normalize_text(anchor) in current_clause
            }:
                return True
    return False


def _is_prop_dominant_state_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """
    判断状态连续性问题的实际变化主体是否为固定道具。

    DeepSeek不必写出“道具”二字。只要固定道具名称或简称明确出现，
    相关子句描述该物件的位置、存在或物理状态变化，并且不存在独立的
    人物位置/服装/身份变化子句，就归入道具连续性。
    """
    alias_map = _known_prop_alias_map(
        facts,
        output,
    )
    if not alias_map:
        return False

    character_ids = {
        _normalize_text(item)
        for item in _known_fact_and_output_character_ids(
            facts,
            output,
        )
        if _normalize_text(item)
    }

    prop_change_clauses: list[str] = []
    human_change_clauses: list[str] = []

    for clause in _issue_clauses(issue):
        normalized_clause = _normalize_text(clause)

        clause_prop_aliases = {
            alias
            for alias in alias_map
            if alias in normalized_clause
        }
        clause_characters = {
            character_id
            for character_id in character_ids
            if character_id in normalized_clause
        }

        if (
            clause_prop_aliases
            and any(
                _normalize_text(marker)
                in normalized_clause
                for marker in PROP_FOCUSED_CHANGE_MARKERS
            )
        ):
            prop_change_clauses.append(clause)

        # “陈默左手前方”只是道具位置参照。
        # 只有不含道具别名的独立人物变化子句才阻止重分类。
        if (
            clause_characters
            and not clause_prop_aliases
            and any(
                _normalize_text(marker)
                in normalized_clause
                for marker in HUMAN_FOCUSED_CHANGE_MARKERS
            )
        ):
            human_change_clauses.append(clause)

    return (
        bool(prop_change_clauses)
        and not human_change_clauses
    )


def _is_true_prop_continuity_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """确认问题主体确为跨镜头发生无依据变化的固定道具。"""
    mentioned_aliases = _mentioned_prop_aliases(
        issue,
        facts,
        output,
    )
    if not mentioned_aliases:
        return False

    has_prop_change = False
    for clause in _issue_clauses(issue):
        normalized_clause = _normalize_text(clause)
        if (
            any(
                alias in normalized_clause
                for alias in mentioned_aliases
            )
            and any(
                _normalize_text(marker) in normalized_clause
                for marker in PROP_FOCUSED_CHANGE_MARKERS
            )
        ):
            has_prop_change = True
            break

    if not has_prop_change:
        return False

    # 人物对道具的接触、持有或释放发生变化时，变化主体是人物状态；
    # 道具只是该人物动作的对象，不能仅因同时提到道具改为PROP。
    if _has_independent_human_state_change(issue, facts, output):
        return False

    blob = _normalize_text(_prop_classification_blob(issue))
    if not (
        "endingstate" in blob
        and "openingstate" in blob
    ):
        return False

    shots = list(_field_value(output, "shots", []) or [])
    shot_id = _shot_id_from_issue(issue, output)
    shot_index = _shot_index_by_id(output, shot_id)
    candidate_indices = (
        [shot_index]
        if shot_index > 0
        else _issue_referenced_shot_indices(issue, output)
    )
    for current_index in candidate_indices:
        if current_index <= 0 or current_index >= len(shots):
            continue
        previous_ending = _field_value(
            shots[current_index - 1], "ending_state", ""
        )
        current_opening = _field_value(
            shots[current_index], "opening_state", ""
        )
        aliases = set(mentioned_aliases)
        previous_clauses = _extract_prop_state_clauses(
            previous_ending, aliases
        )
        current_clauses = _extract_prop_state_clauses(
            current_opening, aliases
        )
        # 两侧都没有道具状态文本只能说明描述省略，不能由模型文字
        # 反推为“道具消失”。出现/消失交由存在性专用分支验证。
        if not previous_clauses or not current_clauses:
            continue
        if not _prop_boundary_state_is_equivalent(
            previous_ending, current_opening, aliases
        ):
            return True

    return False


def _is_unexplained_prop_presence_change(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """确认固定道具被明确描述为消失，但没有镜内合理移出过程。"""
    aliases = _mentioned_prop_aliases(issue, facts, output)
    if not aliases:
        return False

    absence_markers = (
        "消失", "不见", "未出现", "缺失", "凭空", "不存在",
    )
    shot_id = _shot_id_from_issue(issue, output)
    current_index = _shot_index_by_id(output, shot_id)
    shots = list(_field_value(output, "shots", []) or [])
    if current_index <= 0 or current_index >= len(shots):
        return False

    previous_ending = _field_value(
        shots[current_index - 1], "ending_state", ""
    )
    current_opening = _field_value(
        shots[current_index], "opening_state", ""
    )
    previous_presence = bool(_extract_prop_state_clauses(
        previous_ending, set(aliases)
    ))
    current_explicit_absence = (
        any(alias in _normalize_text(current_opening) for alias in aliases)
        and any(
            _normalize_text(marker) in _normalize_text(current_opening)
            for marker in absence_markers
        )
    )
    # 不能把“当前镜未提及”当作消失；但当前opening_state若明确写出
    # “原本……已消失”等存在性断言，本身可作为跨边界的明确证据。
    current_normalized = _normalize_text(current_opening)
    continuity_markers = ("原本", "始终", "之前", "仍", "一直")
    current_asserts_prior_presence = any(
        _normalize_text(marker) in current_normalized
        for marker in continuity_markers
    )
    if not current_explicit_absence:
        return False
    if not previous_presence and not current_asserts_prior_presence:
        return False

    action_text = _normalize_text(
        "\n".join(
            [
                str(_field_value(shots[current_index], "action_path", "")),
                str(_field_value(shots[current_index], "video_prompt", "")),
            ]
        )
    )
    movement_markers = (
        "拿走", "带走", "移出", "移开", "推出", "收起", "遮挡", "销毁",
    )
    has_explained_removal = (
        any(alias in action_text for alias in aliases)
        and any(
            _normalize_text(marker) in action_text
            for marker in movement_markers
        )
    )
    if has_explained_removal:
        return False

    return True


def _has_independent_human_state_change(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    character_ids = {
        _normalize_text(item)
        for item in _known_fact_and_output_character_ids(facts, output)
        if _normalize_text(item)
    }
    prop_aliases = set(_known_prop_alias_map(facts, output))
    human_interaction_markers = (
        "按住", "按在", "离开", "握住", "松开", "触碰", "拿着", "持有",
    )

    for clause in _issue_clauses(issue):
        normalized_clause = _normalize_text(clause)
        has_character = any(
            character_id in normalized_clause
            for character_id in character_ids
        )
        has_prop = any(alias in normalized_clause for alias in prop_aliases)
        has_human_change = any(
            _normalize_text(marker) in normalized_clause
            for marker in HUMAN_FOCUSED_CHANGE_MARKERS
        )
        has_interaction_change = any(
            _normalize_text(marker) in normalized_clause
            for marker in human_interaction_markers
        )
        if has_character and has_human_change and (
            not has_prop or has_interaction_change
        ):
            return True

    return False


def _human_state_signals(
    state_text: Any,
    character_id: str,
    costume_terms: set[str] | None = None,
) -> set[str]:
    """提取同一人物已明确给出的可比较边界状态，不以整段文本比较。"""
    text = str(state_text or "")
    character = re.escape(str(character_id))
    normalized_costumes = {
        _normalize_text(term)
        for term in (costume_terms or set())
        if _normalize_text(term)
    }
    signals: set[str] = set()
    for fragment in re.findall(
        rf"{character}[^。；;\n]*",
        text,
        flags=re.IGNORECASE,
    ):
        for label, pattern in (
            ("position", r"(?:站在|坐在|走到|走向|回到|位于)([^，,。；;\n]+)"),
            ("posture", r"(坐着|坐下|站着|站起身|站立)"),
            ("relation", r"(已离开|离开|按在|按住|握住|松开|触碰|拿着|持有)"),
            ("costume", r"(校服|武侠服|礼服|外套|制服)"),
            ("location_anchor", r"(桌面|课桌|座位|门口|走廊|窗边|楼梯|室外)"),
        ):
            # 保留原始标点边界；先整体归一化会把“，右手已离开”
            # 错并入前面的“站在陈默对面”位置描述。
            match = re.search(pattern, fragment)
            if match:
                value = _normalize_text(match.group(1))
                if label == "position":
                    signals.add(f"{label}:{value}")
                elif label == "relation":
                    signals.add(f"{label}:{value.removeprefix('已')}")
                else:
                    signals.add(f"{label}:{value}")
        normalized_fragment = _normalize_text(fragment)
        for costume in normalized_costumes:
            if costume in normalized_fragment:
                signals.add(f"costume:{costume}")
    return signals


def _analyze_boundary_conflicts(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> dict[str, Any]:
    """以已解析的输出边界字段为权威，确定human/prop/mixed范围。"""
    current_index, phase, canonical_path, source = _resolve_issue_target_shot(
        issue, output
    )
    result: dict[str, Any] = {
        "human_conflicts": [], "prop_conflicts": [], "scope": "unknown",
        "current_index": current_index, "phase": phase,
        "canonical_path": canonical_path, "source": source,
    }
    shots = list(_field_value(output, "shots", []) or [])
    if phase != "opening_state" or current_index <= 0 or current_index >= len(shots):
        return result

    previous_state = _field_value(shots[current_index - 1], "ending_state", "")
    current_state = _field_value(shots[current_index], "opening_state", "")
    costume_terms_by_character: dict[str, set[str]] = {}
    for character in list(_field_value(facts, "characters", []) or []):
        character_id = str(_field_value(character, "character_id", ""))
        if character_id:
            costume_terms_by_character[character_id] = {
                str(term)
                for term in list(
                    _field_value(character, "fixed_costume_terms", []) or []
                )
                if str(term).strip()
            }

    for character_id in _known_fact_and_output_character_ids(facts, output):
        costume_terms = costume_terms_by_character.get(character_id, set())
        previous_signals = _human_state_signals(
            previous_state, character_id, costume_terms
        )
        current_signals = _human_state_signals(
            current_state, character_id, costume_terms
        )
        # 缺失信息及同义复述都不构成冲突；仅比较双方明确给出的、同类不同状态。
        for kind in {item.split(":", 1)[0] for item in previous_signals} & {
            item.split(":", 1)[0] for item in current_signals
        }:
            old_values = {item for item in previous_signals if item.startswith(kind + ":")}
            new_values = {item for item in current_signals if item.startswith(kind + ":")}
            if _human_state_value_sets_are_explicitly_conflicting(
                kind,
                old_values,
                new_values,
            ):
                result["human_conflicts"].append(
                    {"character": character_id, "kind": kind,
                     "previous": sorted(old_values), "current": sorted(new_values)}
                )

    aliases_by_prop: dict[str, set[str]] = {}
    for alias, prop_id in _known_prop_alias_map(facts, output).items():
        aliases_by_prop.setdefault(prop_id, set()).add(alias)
    mentioned_props = set(_mentioned_prop_aliases(
        issue, facts, output
    ).values())
    for prop_id, aliases in aliases_by_prop.items():
        previous_clauses = _extract_prop_state_clauses(previous_state, aliases)
        current_clauses = _extract_prop_state_clauses(current_state, aliases)
        if previous_clauses and current_clauses and not _prop_boundary_state_is_equivalent(
            previous_state, current_state, aliases
        ):
            result["prop_conflicts"].append(
                {"prop": prop_id, "previous": previous_clauses,
                 "current": current_clauses}
            )
        elif (
            prop_id in mentioned_props
            and _is_unexplained_prop_presence_change(issue, facts, output)
        ):
            # 缺少当前道具子句本身不是错误；只有issue与当前字段都明确
            # 指向消失、且没有镜内解释时，才作为存在性变化保留。
            result["prop_conflicts"].append(
                {"prop": prop_id, "previous": previous_clauses,
                 "current": [], "presence_change": True}
            )

    has_human = bool(result["human_conflicts"])
    has_prop = bool(result["prop_conflicts"])
    result["scope"] = "mixed" if has_human and has_prop else (
        "human" if has_human else "prop" if has_prop else "none"
    )
    return result


def _deterministic_prop_physical_boundary_issues(
    facts: ProjectFacts,
    output: DirectorOutput,
) -> list[Issue]:
    """Report only explicit intact/damaged cross-shot contradictions missed by the model."""
    issues: list[Issue] = []
    aliases_by_prop: dict[str, set[str]] = {}
    for alias, prop_id in _known_prop_alias_map(facts, output).items():
        aliases_by_prop.setdefault(prop_id, set()).add(alias)
    intact = ("\u5b8c\u6574", "\u5b8c\u597d", "\u65e0\u635f", "\u65e0\u88c2\u7eb9", "\u672a\u7834\u635f", "\u6ca1\u6709\u88c2\u7eb9", "\u65e0\u7f3a\u53e3")
    damaged = ("\u88c2\u7eb9", "\u5f00\u88c2", "\u7834\u635f", "\u7f3a\u635f", "\u7f3a\u53e3", "\u788e\u88c2", "\u7834\u88c2", "\u51f9\u9677", "\u635f\u574f")
    shots = list(_field_value(output, "shots", []) or [])
    for index in range(1, len(shots)):
        previous = str(_field_value(shots[index - 1], "ending_state", ""))
        current = str(_field_value(shots[index], "opening_state", ""))
        action = _normalize_text("\n".join([str(_field_value(shots[index], "action_path", "")), str(_field_value(shots[index], "video_prompt", ""))]))
        for prop_id, aliases in aliases_by_prop.items():
            old = " ".join(_extract_prop_state_clauses(previous, aliases))
            new = " ".join(_extract_prop_state_clauses(current, aliases))
            # 物理状态常在同一句后半段以“杯身/表面/杯口”等代词出现；
            # 该片段未重复道具名时仍属于已出现道具的同一状态句。
            if any(alias in _normalize_text(previous) for alias in aliases):
                old = _normalize_text(previous)
            if any(alias in _normalize_text(current) for alias in aliases):
                new = _normalize_text(current)
            if not old or not new:
                continue
            old_intact = any(_normalize_text(x) in old for x in intact)
            new_damaged = any(_normalize_text(x) in new for x in damaged)
            explained = _has_explicit_prop_physical_change_process(
                aliases,
                _field_value(shots[index], "opening_state", ""),
                _field_value(shots[index], "first_frame_prompt", ""),
                _field_value(shots[index], "action_path", ""),
                _field_value(shots[index], "video_prompt", ""),
            )
            if old_intact and new_damaged and not explained:
                issues.append(Issue(rule_id="SEMANTIC_PROP_CONTINUITY", severity="error", title="道具连续性冲突", message=f"固定道具{prop_id}在镜头开场前无依据从完整状态变为受损状态。", path=f"director_output.shots[{index}].opening_state", evidence=f"上一镜ending_state: {previous}\n当前镜opening_state: {current}", suggestion="保持道具物理状态连续，或展示明确变化过程。"))
    return issues


def _has_explicit_prop_physical_change_process(
    aliases: set[str],
    opening_state: Any,
    first_frame_prompt: Any,
    action_path: Any,
    video_prompt: Any,
) -> bool:
    """Require a visible causal action, never a damaged-result description alone."""
    opening = _normalize_text(opening_state)
    first_frame = _normalize_text(first_frame_prompt)
    process = _normalize_text("\n".join([str(action_path or ""), str(video_prompt or "")]))
    mentions_prop = any(alias in process for alias in aliases)
    causal_action = any(token in process for token in ("摔", "撞", "砸", "压", "掉落", "碰倒", "击中", "挤裂", "折断", "撕开"))
    causal_link = any(token in process for token in ("导致", "随后", "撞击后", "跌落后", "被摔", "逐渐"))
    # A damaged opening/first frame is already a boundary result; later visual
    # repetition cannot retroactively become the cause.
    damaged_opening = any(token in opening or token in first_frame for token in ("裂纹", "破损", "缺损", "缺口", "碎裂", "破裂"))
    return mentions_prop and causal_action and causal_link and not damaged_opening


def _human_boundary_state_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> Issue | None:
    """仅在输出边界中存在明确人物矛盾时生成STATE。"""
    analysis = _analyze_boundary_conflicts(issue, facts, output)
    if not analysis["human_conflicts"]:
        return None
    current_index = int(analysis["current_index"])
    shots = list(_field_value(output, "shots", []) or [])
    previous_shot, current_shot = shots[current_index - 1], shots[current_index]
    previous_id = str(_field_value(previous_shot, "shot_id", f"S{current_index:02d}"))
    current_id = str(_field_value(current_shot, "shot_id", f"S{current_index + 1:02d}"))
    return Issue(
        rule_id="SEMANTIC_STATE_CONTINUITY",
        severity=str(_field_value(issue, "severity", "error")),
        title="跨镜头状态连续性冲突",
        message=(f"{previous_id} ending_state与{current_id} opening_state中"
                 "人物状态未连续继承。"),
        path=str(analysis["canonical_path"]),
        evidence=(f"{previous_id} ending_state: '{_field_value(previous_shot, 'ending_state', '')}'；"
                  f"{current_id} opening_state: '{_field_value(current_shot, 'opening_state', '')}'"),
        suggestion="让当前镜头opening_state继承上一镜的人物状态。",
    )


def _classify_boundary_conflict_scope(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> str:
    """按输出字段中真实的镜头边界冲突确定唯一规则家族依据。"""
    return str(_analyze_boundary_conflicts(issue, facts, output)["scope"])


def _classify_semantic_issue_scope(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
    boundary: dict[str, Any] | None = None,
) -> str:
    """Classify the subject matter of one issue, not every conflict at its boundary."""
    boundary = boundary or _analyze_boundary_conflicts(issue, facts, output)
    mentioned_props = set(
        _mentioned_prop_aliases(issue, facts, output).values()
    )
    conflicted_props = {
        str(item.get("prop", ""))
        for item in boundary.get("prop_conflicts", [])
    }
    has_prop = bool(mentioned_props & conflicted_props)
    has_human = _has_independent_human_state_change(
        issue,
        facts,
        output,
    )

    if has_human and has_prop:
        return "mixed"
    if has_human:
        return "human"
    if has_prop:
        return "prop"
    return "none"


def _is_inseparable_mixed_boundary_prop_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
    boundary: dict[str, Any] | None = None,
) -> bool:
    """Return True only when a PROP report is one facet of a mixed human/prop boundary.

    A mixed boundary must not suppress an independently established prop error merely
    because it shares a shot with a human error.  The prop is inseparable only when a
    conflicted character's explicit contact/holding relation with that same registered
    prop changes across the very boundary that contains the prop contradiction.
    """
    boundary = boundary or _analyze_boundary_conflicts(issue, facts, output)
    if (
        boundary.get("scope") != "mixed"
        or boundary.get("phase") != "opening_state"
    ):
        return False

    current_index = int(boundary.get("current_index", -1))
    shots = list(_field_value(output, "shots", []) or [])
    if current_index <= 0 or current_index >= len(shots):
        return False

    mentioned_props = set(
        _mentioned_prop_aliases(issue, facts, output).values()
    )
    conflicted_props = {
        str(item.get("prop", ""))
        for item in boundary.get("prop_conflicts", [])
    }
    shared_props = mentioned_props & conflicted_props
    if not shared_props:
        return False

    aliases_by_prop: dict[str, set[str]] = {}
    for alias, prop_id in _known_prop_alias_map(facts, output).items():
        aliases_by_prop.setdefault(prop_id, set()).add(alias)

    previous_state = str(
        _field_value(shots[current_index - 1], "ending_state", "")
    )
    current_state = str(
        _field_value(shots[current_index], "opening_state", "")
    )
    relation_markers = (
        "已离开", "离开", "按在", "按住", "握住", "松开", "触碰", "拿着", "持有",
    )

    for conflict in boundary.get("human_conflicts", []):
        if str(conflict.get("kind", "")) != "relation":
            continue
        character_id = str(conflict.get("character", "")).strip()
        if not character_id:
            continue
        previous_fragments = re.findall(
            rf"{re.escape(character_id)}[^。；;\n]*", previous_state
        )
        current_fragments = re.findall(
            rf"{re.escape(character_id)}[^。；;\n]*", current_state
        )
        for prop_id in shared_props:
            aliases = aliases_by_prop.get(prop_id, set())
            if not aliases:
                continue
            previous_relation = any(
                any(alias in fragment for alias in aliases)
                and any(marker in fragment for marker in relation_markers)
                for fragment in previous_fragments
            )
            current_relation = any(
                any(alias in fragment for alias in aliases)
                and any(marker in fragment for marker in relation_markers)
                for fragment in current_fragments
            )
            if previous_relation and current_relation:
                return True

    return False


def _same_opening_boundary(
    first: Issue,
    second: Issue,
    output: DirectorOutput,
) -> bool:
    """Compare resolved cross-shot opening boundaries, never raw path strings."""
    first_index, first_phase, _, _ = _resolve_issue_target_shot(first, output)
    second_index, second_phase, _, _ = _resolve_issue_target_shot(second, output)
    return (
        first_phase == "opening_state"
        and second_phase == "opening_state"
        and first_index > 0
        and first_index == second_index
    )


def _validate_semantic_issue_family(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> Issue | None:
    """在规则标准化前验证模型声明的PROP问题是否有真实道具变化。"""
    if str(_field_value(issue, "rule_id", "")).upper() != (
        "SEMANTIC_PROP_CONTINUITY"
    ):
        return issue

    # 模型对“当前字段未提及”道具的推断不能替代输出边界证据。
    # 未通过真实道具冲突验证的 PROP 必须在任何规则转换前丢弃，
    # 否则可能经 STATE 规范化后重新参与 PROP 优先分组。
    has_explicit_prop_conflict = (
        _is_true_prop_continuity_issue(issue, facts, output)
        or _is_unexplained_prop_presence_change(issue, facts, output)
    )
    if not has_explicit_prop_conflict:
        return None

    boundary = _analyze_boundary_conflicts(issue, facts, output)
    issue_scope = _classify_semantic_issue_scope(
        issue,
        facts,
        output,
        boundary,
    )
    if issue_scope in {"human", "mixed"} or _is_inseparable_mixed_boundary_prop_issue(
        issue,
        facts,
        output,
        boundary,
    ):
        state_issue = _human_boundary_state_issue(issue, facts, output)
        if state_issue is not None:
            return state_issue

    return issue


def _canonicalize_prop_state_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> Issue | None:
    """
    将被模型编号为状态连续性的固定道具问题标准化为：
    SEMANTIC_PROP_CONTINUITY + 当前镜opening_state路径。
    """
    if not _is_prop_continuity_issue(
        issue,
        facts,
        output,
    ):
        return None

    incoming_rule_id = str(
        _field_value(issue, "rule_id", "")
    ).upper()

    # 已经是稳定道具规则时，仅统一标题，不改写历史路径与证据。
    if incoming_rule_id == "SEMANTIC_PROP_CONTINUITY":
        return Issue(
            rule_id="SEMANTIC_PROP_CONTINUITY",
            severity=str(
                _field_value(issue, "severity", "error")
            ),
            title="道具连续性冲突",
            message=str(
                _field_value(issue, "message", "")
            ),
            path=str(
                _field_value(issue, "path", "")
            ),
            evidence=str(
                _field_value(issue, "evidence", "")
            ),
            suggestion=str(
                _field_value(
                    issue,
                    "suggestion",
                    "让固定道具保持跨镜头连续。",
                )
            ),
        )

    mentioned_aliases = _mentioned_prop_aliases(
        issue,
        facts,
        output,
    )
    canonical_prop_names = sorted(
        set(mentioned_aliases.values()),
        key=len,
        reverse=True,
    )
    prop_label = (
        canonical_prop_names[0]
        if canonical_prop_names
        else "固定道具"
    )
    prop_aliases = _prop_aliases(prop_label)

    shots = list(
        _field_value(output, "shots", []) or []
    )

    referenced_indices = _issue_referenced_shot_indices(
        issue,
        output,
    )
    shot_id = _shot_id_from_issue(
        issue,
        output,
    )
    shot_index = (
        _shot_index_by_id(output, shot_id)
        if shot_id
        else -1
    )

    candidate_indices: list[int] = []
    if shot_index > 0:
        candidate_indices.append(shot_index)

    candidate_indices.extend(
        index
        for index in reversed(referenced_indices)
        if (
            index > 0
            and index not in candidate_indices
        )
    )
    candidate_indices.extend(
        index
        for index in range(len(shots) - 1, 0, -1)
        if index not in candidate_indices
    )

    for current_index in candidate_indices:
        previous_shot = shots[current_index - 1]
        current_shot = shots[current_index]

        previous_ending = str(
            _field_value(
                previous_shot,
                "ending_state",
                "",
            )
        ).strip()
        current_opening = str(
            _field_value(
                current_shot,
                "opening_state",
                "",
            )
        ).strip()
        current_first_frame = str(
            _field_value(
                current_shot,
                "first_frame_prompt",
                "",
            )
        ).strip()

        normalized_previous = _normalize_text(
            previous_ending
        )
        normalized_current = _normalize_text(
            current_opening
        )
        normalized_first = _normalize_text(
            current_first_frame
        )

        previous_mentions_prop = any(
            alias in normalized_previous
            for alias in prop_aliases
        )
        current_mentions_prop = any(
            alias in normalized_current
            or alias in normalized_first
            for alias in prop_aliases
        )

        if not (
            previous_mentions_prop
            and current_mentions_prop
        ):
            continue

        current_shot_id = str(
            _field_value(
                current_shot,
                "shot_id",
                f"S{current_index + 1:02d}",
            )
        )
        previous_shot_id = str(
            _field_value(
                previous_shot,
                "shot_id",
                f"S{current_index:02d}",
            )
        )

        return Issue(
            rule_id="SEMANTIC_PROP_CONTINUITY",
            severity=str(
                _field_value(issue, "severity", "error")
            ),
            title="道具连续性冲突",
            message=(
                f"{previous_shot_id} ending_state中"
                f"{prop_label}保持在既定位置或状态，"
                f"但{current_shot_id} opening_state"
                "没有继承该道具状态，且没有人物操作、"
                "镜头过渡或固定事实事件解释其变化。"
            ),
            path=(
                f"director_output.shots[{current_index}]"
                ".opening_state"
            ),
            evidence=(
                f"{previous_shot_id} ending_state: "
                f"'{previous_ending}'；"
                f"{current_shot_id} opening_state: "
                f"'{current_opening}'；"
                f"{current_shot_id} first_frame_prompt: "
                f"'{current_first_frame}'"
            ),
            suggestion=(
                "让当前镜头opening_state继承上一镜中固定道具的"
                "位置和物理状态。需要改变时，应在action_path和"
                "video_prompt中加入明确、可见的移动或变化过程。"
            ),
        )

    # 无法安全确定镜头边界时，只改规则类型，不猜测新路径。
    return Issue(
        rule_id="SEMANTIC_PROP_CONTINUITY",
        severity=str(
            _field_value(issue, "severity", "error")
        ),
        title="道具连续性冲突",
        message=str(
            _field_value(issue, "message", "")
        ),
        path=str(
            _field_value(issue, "path", "")
        ),
        evidence=str(
            _field_value(issue, "evidence", "")
        ),
        suggestion=str(
            _field_value(
                issue,
                "suggestion",
                "让固定道具保持跨镜头连续。",
            )
        ),
    )


def _is_prop_continuity_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    rule_id = str(
        _field_value(issue, "rule_id", "")
    ).upper()

    if rule_id == "SEMANTIC_PROP_CONTINUITY":
        return True

    if not rule_id.startswith("SEMANTIC_"):
        return False

    # 已有稳定的人物身份规则绝不重分类。
    if rule_id == "SEMANTIC_IDENTITY_CONTINUITY":
        return False

    blob = _prop_classification_blob(issue)
    normalized_blob = _normalize_text(blob)

    mentioned_props = _mentioned_prop_aliases(
        issue,
        facts,
        output,
    )

    has_explicit_prop_focus = (
        "道具" in blob
        or "固定物件" in blob
        or "固定物品" in blob
        or "prop" in normalized_blob
    )

    has_continuity_marker = any(
        _normalize_text(marker) in normalized_blob
        for marker in PROP_CONTINUITY_MARKERS
    )

    # 对已有SEMANTIC_STATE_CONTINUITY采取更严格标准：
    # 必须明确提到facts中的固定道具，且正文聚焦该道具变化。
    # 仅在证据中顺带出现水滴、信封等场景元素，不改写规则类型。
    if rule_id == "SEMANTIC_STATE_CONTINUITY":
        boundary = _analyze_boundary_conflicts(issue, facts, output)
        boundary_props = {
            str(item.get("prop", ""))
            for item in boundary.get("prop_conflicts", [])
        }
        mentioned_prop_ids = set(mentioned_props.values())
        # A model may call a pure prop physical contradiction "STATE".  The
        # output boundary is authoritative: only reclassify when it contains
        # no independent human contradiction and the issue names that exact
        # conflicted registered prop.
        if (
            boundary.get("scope") == "prop"
            and bool(mentioned_prop_ids & boundary_props)
        ):
            return True
        return (
            bool(mentioned_props)
            and has_continuity_marker
            and has_explicit_prop_focus
        )

    return (
        (bool(mentioned_props) or has_explicit_prop_focus)
        and has_continuity_marker
    )



def _semantic_continuity_issue_has_explicit_source_conflict(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """最终连续性错误必须由实际源字段中的显式互斥状态支持。"""
    rule_id = str(_field_value(issue, "rule_id", "")).upper()
    if rule_id not in {
        "SEMANTIC_STATE_CONTINUITY",
        "SEMANTIC_PROP_CONTINUITY",
    }:
        return True

    current_index, phase, _, _ = _resolve_issue_target_shot(issue, output)
    shots = list(_field_value(output, "shots", []) or [])
    if current_index < 0 or current_index >= len(shots):
        # 无法解析源字段时保持保守，不在此处删除。
        return True

    current_shot = shots[current_index]

    if phase == "opening_state":
        if current_index <= 0:
            return True
        previous_ending = _field_value(
            shots[current_index - 1], "ending_state", ""
        )
        current_opening = _field_value(
            current_shot, "opening_state", ""
        )
        if rule_id == "SEMANTIC_STATE_CONTINUITY":
            return _state_texts_have_explicit_continuity_conflict(
                previous_ending, current_opening, facts, output
            )

        aliases = set(_mentioned_prop_aliases(issue, facts, output))
        if not aliases:
            return True
        previous_clauses = _extract_prop_state_clauses(
            previous_ending, aliases
        )
        current_clauses = _extract_prop_state_clauses(
            current_opening, aliases
        )
        if previous_clauses and current_clauses:
            return not _prop_boundary_state_is_equivalent(
                previous_ending, current_opening, aliases
            )
        return _is_unexplained_prop_presence_change(issue, facts, output)

    if phase == "first_frame_prompt":
        opening = _field_value(current_shot, "opening_state", "")
        first_frame = _field_value(
            current_shot, "first_frame_prompt", ""
        )
        if rule_id == "SEMANTIC_STATE_CONTINUITY":
            return _state_texts_have_explicit_continuity_conflict(
                opening, first_frame, facts, output
            )

        aliases = set(_mentioned_prop_aliases(issue, facts, output))
        if not aliases:
            return True
        opening_clauses = _extract_prop_state_clauses(opening, aliases)
        first_clauses = _extract_prop_state_clauses(first_frame, aliases)
        return bool(
            opening_clauses
            and first_clauses
            and not _prop_boundary_state_is_equivalent(
                opening, first_frame, aliases
            )
        )

    # action_path/video_prompt等阶段可能描述镜内变化，继续交给既有规则处理。
    return True



FIRST_FRAME_CONFLICT_MARKERS = (
    "首帧状态",
    "第一帧",
    "first_frame_prompt",
    "位置跳变",
    "无依据跳变",
    "无过渡",
    "已经站在",
    "已站在",
    "直接出现在",
    "与开场状态",
    "与opening_state",
)


def _issue_referenced_shot_indices(
    issue: Issue,
    output: DirectorOutput,
) -> list[int]:
    """
    从rule正文和path中提取所有镜头引用。

    连续性问题常同时出现S04和S05，当前冲突镜头取时间上更后的一个。
    """
    shots = list(
        _field_value(output, "shots", []) or []
    )
    blob = "\n".join(
        [
            str(_field_value(issue, "title", "")),
            str(_field_value(issue, "message", "")),
            str(_field_value(issue, "path", "")),
            str(_field_value(issue, "evidence", "")),
        ]
    )

    result: set[int] = set()

    shot_id_to_index = {
        str(
            _field_value(shot, "shot_id", "")
        ).upper(): index
        for index, shot in enumerate(shots)
    }

    for matched in re.findall(
        r"\bS\d+\b",
        blob,
        flags=re.IGNORECASE,
    ):
        index = shot_id_to_index.get(
            matched.upper()
        )
        if index is not None:
            result.add(index)

    for matched in re.findall(
        r"shots\[(\d+)\]",
        blob,
        flags=re.IGNORECASE,
    ):
        index = int(matched)
        if 0 <= index < len(shots):
            result.add(index)

    for matched in re.findall(
        r"shots\.S(\d+)",
        blob,
        flags=re.IGNORECASE,
    ):
        shot_id = f"S{matched}".upper()
        index = shot_id_to_index.get(shot_id)
        if index is not None:
            result.add(index)

    return sorted(result)


def _human_state_value_sets_are_explicitly_conflicting(
    kind: str,
    old_values: set[str],
    new_values: set[str],
) -> bool:
    """Only mutually exclusive human signals count as a continuity conflict."""
    if not old_values or not new_values:
        return False
    if not old_values.isdisjoint(new_values):
        return False

    old_raw = {item.split(":", 1)[1] for item in old_values}
    new_raw = {item.split(":", 1)[1] for item in new_values}
    for old_value in old_raw:
        for new_value in new_raw:
            if old_value in new_value or new_value in old_value:
                return False

    if kind == "position":
        # “陈默对面”与“他对面”是同一关系的代词复述，不是位置跳变。
        relation_suffixes = ("对面", "旁边", "身边", "前方", "后方")
        pronoun_prefixes = ("他", "她", "对方", "其")
        for old_value in old_raw:
            for new_value in new_raw:
                for suffix in relation_suffixes:
                    if not (old_value.endswith(suffix) and new_value.endswith(suffix)):
                        continue
                    if (
                        old_value.startswith(pronoun_prefixes)
                        or new_value.startswith(pronoun_prefixes)
                    ):
                        return False

    return True


def _scene_light_state_signals(
    state_text: Any,
) -> set[str]:
    """Extract only explicit, normalized scene-light temperature states."""
    text = _normalize_text(state_text)
    signals: set[str] = set()

    cold_markers = (
        "光线变冷",
        "变为冷光",
        "冷光",
        "冷色光",
        "冷色调",
    )
    warm_markers = (
        "光线变暖",
        "变为暖光",
        "恢复为温暖",
        "温暖明亮",
        "暖光",
        "暖色光",
        "暖色调",
    )

    if any(_normalize_text(marker) in text for marker in cold_markers):
        signals.add("temperature:cold")
    if any(_normalize_text(marker) in text for marker in warm_markers):
        signals.add("temperature:warm")

    return signals


def _scene_light_states_are_explicitly_conflicting(
    previous_state: Any,
    current_state: Any,
) -> bool:
    """Return True only for an explicit cold/warm scene-light reversal."""
    previous = _scene_light_state_signals(previous_state)
    current = _scene_light_state_signals(current_state)

    return (
        "temperature:cold" in previous
        and "temperature:warm" in current
    ) or (
        "temperature:warm" in previous
        and "temperature:cold" in current
    )

def _state_texts_have_explicit_continuity_conflict(
    previous_state: Any,
    current_state: Any,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> bool:
    """Compare only explicit, same-family human, scene, or fixed-prop evidence."""
    if _scene_light_states_are_explicitly_conflicting(
        previous_state,
        current_state,
    ):
        return True
    costume_terms_by_character: dict[str, set[str]] = {}
    for character in list(_field_value(facts, "characters", []) or []):
        character_id = str(_field_value(character, "character_id", ""))
        if character_id:
            costume_terms_by_character[character_id] = {
                str(term) for term in list(
                    _field_value(character, "fixed_costume_terms", []) or []
                ) if str(term).strip()
            }
    for character_id in _known_fact_and_output_character_ids(facts, output):
        before = _human_state_signals(
            previous_state, character_id,
            costume_terms_by_character.get(character_id, set()),
        )
        after = _human_state_signals(
            current_state, character_id,
            costume_terms_by_character.get(character_id, set()),
        )
        before_kinds = {item.split(":", 1)[0] for item in before}
        after_kinds = {item.split(":", 1)[0] for item in after}
        for kind in before_kinds & after_kinds:
            old_values = {item for item in before if item.startswith(kind + ":")}
            new_values = {item for item in after if item.startswith(kind + ":")}
            if _human_state_value_sets_are_explicitly_conflicting(
                kind, old_values, new_values
            ):
                return True
    aliases_by_prop: dict[str, set[str]] = {}
    for alias, prop_id in _known_prop_alias_map(facts, output).items():
        aliases_by_prop.setdefault(prop_id, set()).add(alias)
    return any(
        _extract_prop_state_clauses(previous_state, aliases)
        and _extract_prop_state_clauses(current_state, aliases)
        and not _prop_boundary_state_is_equivalent(previous_state, current_state, aliases)
        for aliases in aliases_by_prop.values()
    )


def _canonicalize_first_frame_state_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> Issue | None:
    """
    当跨镜头边界本身连续，但first_frame_prompt没有继承opening_state时，
    将DeepSeek含混或自相矛盾的报告标准化为准确的首帧冲突。

    规则ID仍使用SEMANTIC_STATE_CONTINUITY，以保持状态连续性规则族稳定。
    """
    rule_id = str(
        _field_value(issue, "rule_id", "")
    ).upper()
    if rule_id != "SEMANTIC_STATE_CONTINUITY":
        return None

    blob = "\n".join(
        [
            str(_field_value(issue, "title", "")),
            str(_field_value(issue, "message", "")),
            str(_field_value(issue, "path", "")),
            str(_field_value(issue, "evidence", "")),
        ]
    )
    normalized_blob = _normalize_text(blob)

    mentions_first_frame = (
        "firstframeprompt" in normalized_blob
        or "第一帧" in blob
        or "首帧" in blob
    )
    if not mentions_first_frame:
        return None

    if not any(
        _normalize_text(marker) in normalized_blob
        for marker in FIRST_FRAME_CONFLICT_MARKERS
    ):
        return None

    shots = list(
        _field_value(output, "shots", []) or []
    )
    referenced_indices = _issue_referenced_shot_indices(
        issue,
        output,
    )

    candidate_indices = [
        index
        for index in reversed(referenced_indices)
        if index > 0
    ]

    # Only fall back to a global scan when neither path nor prose resolves a
    # target shot.  Scanning every shot for an otherwise resolved S05 issue
    # can manufacture an unrelated S02 first-frame finding.
    if not candidate_indices:
        candidate_indices.extend(range(len(shots) - 1, 0, -1))

    for current_index in candidate_indices:
        previous_shot = shots[current_index - 1]
        current_shot = shots[current_index]

        previous_ending_raw = str(
            _field_value(
                previous_shot,
                "ending_state",
                "",
            )
        ).strip()
        current_opening_raw = str(
            _field_value(
                current_shot,
                "opening_state",
                "",
            )
        ).strip()
        first_frame_raw = str(
            _field_value(
                current_shot,
                "first_frame_prompt",
                "",
            )
        ).strip()

        previous_ending = _normalize_text(
            previous_ending_raw
        )
        current_opening = _normalize_text(
            current_opening_raw
        )
        first_frame = _normalize_text(
            first_frame_raw
        )

        if (
            not previous_ending
            or not current_opening
            or not first_frame
        ):
            continue

        # Text can legitimately differ in omitted non-conflicting detail.  The
        # boundary is continuous when no explicit human/prop state contradicts
        # it; only then can the first frame own the error path.
        if _state_texts_have_explicit_continuity_conflict(
            previous_ending_raw, current_opening_raw, facts, output
        ):
            continue

        # A shared phrase is not proof of inheritance.  Require an actual
        # explicit conflict before attributing an issue to first_frame_prompt.
        if not _state_texts_have_explicit_continuity_conflict(
            current_opening_raw, first_frame_raw, facts, output
        ):
            continue

        current_shot_id = str(
            _field_value(
                current_shot,
                "shot_id",
                f"S{current_index + 1:02d}",
            )
        )
        previous_shot_id = str(
            _field_value(
                previous_shot,
                "shot_id",
                f"S{current_index:02d}",
            )
        )

        return Issue(
            rule_id="SEMANTIC_STATE_CONTINUITY",
            severity=str(
                _field_value(
                    issue,
                    "severity",
                    "error",
                )
            ),
            title="首帧状态与开场状态冲突",
            message=(
                f"{current_shot_id} opening_state已完整继承"
                f"{previous_shot_id} ending_state，但"
                f"{current_shot_id} first_frame_prompt没有继承该开场状态，"
                "在镜头第一帧发生了无过渡的位置、姿态或持续状态跳变。"
                "首帧属于镜头开始瞬间，不能跳过必要的移动或变化过程。"
            ),
            path=(
                f"director_output.shots[{current_index}]"
                ".first_frame_prompt"
            ),
            evidence=(
                f"{previous_shot_id} ending_state: "
                f"'{previous_ending_raw}'；"
                f"{current_shot_id} opening_state: "
                f"'{current_opening_raw}'；"
                f"{current_shot_id} first_frame_prompt: "
                f"'{first_frame_raw}'"
            ),
            suggestion=(
                "让first_frame_prompt直接继承opening_state。"
                "人物位置、姿态或道具状态的后续变化应写入"
                "action_path和video_prompt，并提供可见的变化过程。"
            ),
        )

    return None


def _canonicalize_semantic_issue(
    issue: Issue,
    facts: ProjectFacts,
    output: DirectorOutput,
) -> Issue:
    """
    将DeepSeek随机编号的SEMANTIC_X映射为稳定规则ID。

    当前只标准化证据明确的持久道具连续性问题：
    固定道具无依据消失、出现、位置或状态跳变。
    """
    first_frame_issue = (
        _canonicalize_first_frame_state_issue(issue, facts, output)
    )
    if first_frame_issue is not None:
        return first_frame_issue

    prop_issue = _canonicalize_prop_state_issue(
        issue,
        facts,
        output,
    )
    if prop_issue is not None:
        return prop_issue

    return issue



ACTION_FEASIBILITY_PATTERNS = (
    (
        "位移动作",
        re.compile(
            r"站起|起身|坐下|蹲下|走到|走向|走回|"
            r"跑到|跑向|绕过|越过|靠近|离开|"
            r"转身|后退|前进|冲向|扑向"
        ),
        0.70,
    ),
    (
        "物件交互",
        re.compile(
            r"拿起|放下|放回|打开|关闭|翻动|翻开|"
            r"合上|收回|按住|触碰|抓住|松开|"
            r"递出|接过|掏出|拔出|推开|拉开"
        ),
        0.45,
    ),
    (
        "视线动作",
        re.compile(
            r"抬眼|低头|抬头|回头|转头|看向|"
            r"望向|闭眼|睁眼"
        ),
        0.35,
    ),
    (
        "肢体动作",
        re.compile(
            r"抬手|放手|伸手|挥手|点头|摇头|"
            r"后仰|前倾|跪下|起立"
        ),
        0.40,
    ),
    (
        "画面事件",
        re.compile(
            r"闪灭|熄灭|亮起|切黑|爆炸|倒塌|"
            r"破碎|消失|出现|悬浮|落下|升起"
        ),
        0.20,
    ),
)

ACTION_NEGATION_MARKERS = (
    "没有",
    "未",
    "不",
    "禁止",
    "避免",
    "不得",
    "并未",
)


def _shot_duration_seconds(shot: Any) -> float:
    final_duration = _field_value(
        shot,
        "final_duration",
        None,
    )
    if final_duration is not None:
        try:
            return float(final_duration)
        except (TypeError, ValueError):
            pass

    try:
        start_time = float(
            _field_value(shot, "start_time", 0.0)
        )
        end_time = float(
            _field_value(shot, "end_time", 0.0)
        )
        return max(0.0, end_time - start_time)
    except (TypeError, ValueError):
        return 0.0


def _action_narrative(action_path: Any) -> str:
    text = str(action_path or "")
    for separator in (
        "\n\n固定事实事件",
        "\n固定事实事件",
        "固定事实事件：",
        "固定事实事件:",
    ):
        if separator in text:
            text = text.split(separator, 1)[0]
    return text.strip()


def _is_negated_action_match(
    text: str,
    start: int,
) -> bool:
    prefix = text[
        max(0, start - 6):start
    ]
    return any(
        marker in prefix
        for marker in ACTION_NEGATION_MARKERS
    )


def _action_feasibility_metrics(
    shot: Any,
) -> dict[str, Any]:
    narrative = _action_narrative(
        _field_value(shot, "action_path", "")
    )
    matched_actions: list[str] = []
    estimated_min_seconds = 0.0

    for _, pattern, weight in ACTION_FEASIBILITY_PATTERNS:
        for matched in pattern.finditer(narrative):
            if _is_negated_action_match(
                narrative,
                matched.start(),
            ):
                continue

            matched_actions.append(
                matched.group(0)
            )
            estimated_min_seconds += weight

    slow_count = narrative.count("缓慢")
    continuous_count = narrative.count("连续")
    estimated_min_seconds += slow_count * 0.50
    estimated_min_seconds += continuous_count * 0.30

    duration = _shot_duration_seconds(shot)

    return {
        "duration": duration,
        "action_count": len(matched_actions),
        "estimated_min_seconds": round(
            estimated_min_seconds,
            2,
        ),
        "matched_actions": matched_actions,
        "narrative": narrative,
    }


def _is_extreme_action_overload(
    metrics: dict[str, Any],
) -> bool:
    duration = float(
        metrics.get("duration", 0.0)
    )
    action_count = int(
        metrics.get("action_count", 0)
    )
    estimated_min = float(
        metrics.get(
            "estimated_min_seconds",
            0.0,
        )
    )

    if duration <= 0:
        return False

    # 保守阈值：只确定性捕获非常明显的动作过载。
    # 普通的2秒三事件、5秒连续表演不会触发。
    return (
        action_count >= 8
        and estimated_min > duration * 1.8
        and estimated_min - duration >= 2.0
    )



EVENT_ORDER_NARRATIVE_FIELDS = (
    "action_path",
    "video_prompt",
)


def _all_required_events_present(
    required_events: list[str],
    field_text: Any,
) -> bool:
    normalized_text = _normalize_text(field_text)
    if not normalized_text:
        return False

    return all(
        _normalize_text(event) in normalized_text
        for event in required_events
        if _normalize_text(event)
    )


def _actual_event_order(
    required_events: list[str],
    field_text: Any,
) -> list[str]:
    """
    返回固定事件在字段中的首次出现顺序。

    只在全部固定事件都存在时调用。
    """
    normalized_text = _normalize_text(field_text)
    positioned_events: list[tuple[int, int, str]] = []

    for expected_index, event in enumerate(required_events):
        normalized_event = _normalize_text(event)
        if not normalized_event:
            continue

        position = normalized_text.find(normalized_event)
        if position < 0:
            return []

        positioned_events.append(
            (
                position,
                expected_index,
                str(event),
            )
        )

    positioned_events.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )
    return [
        item[2]
        for item in positioned_events
    ]


def _event_order_precheck(
    facts: ProjectFacts,
    output: DirectorOutput,
) -> list[Issue]:
    """
    确定性检查facts.required_events之间的相对顺序。

    仅在同一叙事字段中满足以下条件时报告：
    1. 至少有两个固定事件；
    2. 所有固定事件的精确短语都存在；
    3. 这些事件无法按facts要求的顺序匹配。

    固定事件缺失由硬规则处理；额外动作不影响相对顺序。
    """
    issues: list[Issue] = []

    for output_index, output_shot in enumerate(output.shots):
        facts_shot = _shot_by_id(
            facts,
            output_shot.shot_id,
        )
        if facts_shot is None:
            continue

        required_events = [
            str(item)
            for item in (
                _field_value(
                    facts_shot,
                    "required_events",
                    [],
                )
                or []
            )
            if str(item).strip()
        ]
        if len(required_events) < 2:
            continue

        wrong_fields: list[
            tuple[str, list[str], str]
        ] = []

        for field_name in EVENT_ORDER_NARRATIVE_FIELDS:
            field_text = str(
                _field_value(
                    output_shot,
                    field_name,
                    "",
                )
                or ""
            )

            if not _all_required_events_present(
                required_events,
                field_text,
            ):
                continue

            if _events_appear_in_required_order(
                required_events,
                field_text,
            ):
                continue

            actual_order = _actual_event_order(
                required_events,
                field_text,
            )
            if not actual_order:
                continue

            wrong_fields.append(
                (
                    field_name,
                    actual_order,
                    field_text,
                )
            )

        if not wrong_fields:
            continue

        primary_field, actual_order, primary_text = (
            wrong_fields[0]
        )
        expected_text = " → ".join(required_events)
        actual_text = " → ".join(actual_order)
        field_names = "、".join(
            field_name
            for field_name, _, _ in wrong_fields
        )

        issues.append(
            Issue(
                rule_id="SEMANTIC_EVENT_ORDER",
                severity="error",
                title="固定事件顺序错误",
                message=(
                    f"{output_shot.shot_id}的"
                    f"{field_names}中固定事件顺序与facts相反。"
                    f"facts要求：{expected_text}；"
                    f"实际顺序：{actual_text}。"
                ),
                path=(
                    f"director_output.shots[{output_index}]"
                    f".{primary_field}"
                ),
                evidence=(
                    f"{primary_field}: {primary_text}"
                ),
                suggestion=(
                    "保留全部固定事件的精确内容，"
                    "并按facts.required_events规定的先后顺序排列。"
                ),
            )
        )

    return issues


def _action_feasibility_precheck(
    facts: ProjectFacts,
    output: DirectorOutput,
) -> list[Issue]:
    """
    对极端动作过载做确定性预检。

    这不是精确动作计时器，只捕获无需主观判断也能确认的情况：
    极短镜头内塞入大量完整位移、取放物件和姿态变化。
    """
    issues: list[Issue] = []

    for index, shot in enumerate(output.shots):
        metrics = _action_feasibility_metrics(shot)
        if not _is_extreme_action_overload(metrics):
            continue

        matched_actions = list(
            metrics["matched_actions"]
        )
        evidence_actions = "、".join(
            matched_actions[:12]
        )
        if len(matched_actions) > 12:
            evidence_actions += "等"

        issues.append(
            Issue(
                rule_id=(
                    "SEMANTIC_ACTION_FEASIBILITY"
                ),
                severity="error",
                title="动作无法在镜头时长内完成",
                message=(
                    f"{shot.shot_id}时长"
                    f"{metrics['duration']:g}秒，"
                    f"action_path包含至少"
                    f"{metrics['action_count']}个明确动作节点，"
                    f"保守估算完成时间约"
                    f"{metrics['estimated_min_seconds']:g}秒，"
                    "无法以自然、清晰、连续的节奏完成。"
                ),
                path=(
                    f"director_output.shots[{index}]"
                    ".action_path"
                ),
                evidence=(
                    f"动作节点：{evidence_actions}；"
                    f"镜头时长：{metrics['duration']:g}秒"
                ),
                suggestion=(
                    "删除非必要动作、拆分镜头，"
                    "或延长镜头时长。"
                ),
            )
        )

    return issues


def _identity_continuity_precheck(
    facts: ProjectFacts,
    output: DirectorOutput,
) -> list[Issue]:
    """
    对明显的“同一角色变成另一人”做确定性预检。

    角色换装、发型被风吹动、身份觉醒、能力变化不等于换人。
    只有明确描述为另一名人物、不同脸或身份被替换时才报错。
    """
    issues: list[Issue] = []

    known_character_ids = {
        character.character_id
        for character in facts.characters
    }

    for index, shot in enumerate(output.shots):
        shot_text = "\n".join(
            [
                str(shot.opening_state or ""),
                str(shot.action_path or ""),
                str(shot.performance or ""),
                str(shot.ending_state or ""),
                str(shot.video_prompt or ""),
            ]
        )

        matched = [
            pattern
            for pattern in IDENTITY_CHANGE_PATTERNS
            if re.search(pattern, shot_text, flags=re.IGNORECASE)
        ]

        if not matched:
            continue

        present_ids = [
            character_id
            for character_id in shot.characters
            if character_id in known_character_ids
        ]

        issues.append(
            Issue(
                rule_id="SEMANTIC_IDENTITY_CONTINUITY",
                severity="error",
                title="人物身份连续性被破坏",
                message=(
                    f"{shot.shot_id}仍使用锁定角色"
                    f"{'、'.join(present_ids) if present_ids else 'ID'}，"
                    "但正文明确把该角色替换成另一名不同人物。"
                ),
                path=f"director_output.shots[{index}].action_path",
                evidence="；".join(matched),
                suggestion=(
                    "保留同一人物的脸型、五官和身份一致性。"
                    "变身只能改变剧本允许改变的服装、状态或能力；"
                    "除非facts明确规定换人、分身、附身或身体交换。"
                ),
            )
        )

    return issues


def semantic_audit(
    facts: ProjectFacts,
    output: DirectorOutput,
    hard_issues: list[Issue] | None = None,
) -> list[Issue]:
    deterministic_issues = (
        _identity_continuity_precheck(
            facts,
            output,
        )
        + _deterministic_prop_physical_boundary_issues(
            facts,
            output,
        )
        + _action_feasibility_precheck(
            facts,
            output,
        )
        + _event_order_precheck(
            facts,
            output,
        )
    )

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("未配置DEEPSEEK_API_KEY")

    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
    base_url = os.getenv(
        "DEEPSEEK_BASE_URL",
        "https://api.deepseek.com",
    ).strip()

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    system = """
你是AI影视制作方案语义审计器，不是导演，不得重新创作。

比较facts.json和director_output.json，只报告确定存在的违规。

必须检查：
1. 剧情、台词、镜头归属是否被改写。
2. 固定事件是否提前、延后、遗漏或出现在错误镜头。
3. 人物服装、道具、地点和动作状态是否冲突。
4. 同一character_id在所有镜头中必须代表同一个人。
5. “变身、觉醒、换装、进入战斗状态”默认只允许改变剧本明确规定的服装、状态或能力，
   不允许擅自变成另一名人物，不允许脸型、五官、年龄、性别或身份被替换。
6. 只有facts明确规定换人、分身、附身、身体交换、替身或易容时，人物身份变化才允许。
7. 即使facts没有逐字写“禁止换脸”，只要同一character_id被描述为
   “不再是原来的人、另一名完全不同的人、五官和身份改变”，也必须报错。
8. 场景空间和物理动作是否冲突。
9. 动作是否能在镜头时长内完成。
10. 首帧是否包含连续动作过程。
11. 正文是否与negative_constraints冲突。
12. 摄影风格是否被错误理解成人物国籍或身份。
13. 用户输入中的hard_issues已经由确定性规则报告，不得重复报告同一错误。
14. 同一根因、同一路径或同一镜头交界处的多个状态矛盾必须合并成一条问题，
    在message和evidence中列出多个冲突点，不得拆成多条重复扣分。
15. 当opening_state已经构成与上一镜ending_state的连续性冲突时，
    不得再分别对first_frame_prompt、video_prompt、action_path重复报告同一状态。
    只能输出一条“跨镜头状态连续性冲突”。
16. action_path和video_prompt没有重复声明opening_state中的静态站位、手部状态或道具位置，
    不等于冲突。只有它们明确写出相反状态时才可报告。
17. “说出台词”只是正常动作描述，不代表存在台词错误。只有说话人、台词内容、
    台词所属镜头、台词顺序或擅加台词发生错误时，才可单独报告台词问题。
18. first_frame_prompt若只是复现同一个错误opening_state，应并入连续性主问题，
    不得单独扣分。
19. path必须指向实际包含证据的字段，不得把opening_state或first_frame_prompt中的内容
    错误归因到action_path或video_prompt。
20. 语义审计只补充硬规则无法判断的语义问题。
21. 如果hard_issues已经用EVENT_TOO_EARLY、FORBIDDEN_EVENT或EVENT_WRONG_SHOT
    报告了某个动作，不得再以“动作时长不足、动作可行性不足、应移到其他镜头”
    等理由重复报告同一个动作。相同动作、相同根因、相同修复目标只能扣分一次。
22. 固定道具无依据消失、出现、位置跳变或状态跳变时，
    rule_id必须使用SEMANTIC_PROP_CONTINUITY，不得使用随机SEMANTIC_1、
    SEMANTIC_2、SEMANTIC_3等编号。
23. 人物位置、姿态、服装或画面持续状态跨镜头冲突时，
    rule_id使用SEMANTIC_STATE_CONTINUITY。
24. 如果分析过程最终得出“无冲突、合理、不矛盾、不构成违规”，
    必须删除该候选问题，不得把它放入issues。
25. 每条issue的message必须明确确认违规成立。禁止先提出怀疑，随后在同一条
    message中得出“无冲突”，却仍以error返回。
26. 不得把opening_state中的静态状态与同一镜头action_path中随后发生的动作
    误判为冲突。opening_state描述镜头开始，action_path描述镜头内后续变化。
27. 如果hard_issues已包含UNKNOWN_CHARACTER或UNKNOWN_PROP，不得再针对同一未知人物
    或道具在action_path、video_prompt、first_frame_prompt、generation_segments、
    negative_constraints中的重复出现另行报告。
28. SEMANTIC_STATE_CONTINUITY只用于相邻镜头边界上的人物位置、姿态、服装、道具状态、
    光线或持续画面状态不一致。未知人物、第三名人物、未知道具、禁用事件和
    negative_constraints执行失败不得使用此rule_id。
29. 同一个未知人物在多个字段出现仍是一个UNKNOWN_CHARACTER根因，不得按字段拆分扣分。
30. 如果EVENT_TOO_EARLY、FORBIDDEN_EVENT或EVENT_WRONG_SHOT已经报告某个动作，
    不得再因为该动作导致下一镜opening_state与action_path不一致而追加
    SEMANTIC_STATE_CONTINUITY。该状态矛盾是同一事件错误的派生结果。
31. SEMANTIC_PROP_CONTINUITY只用于问题主体明确是facts固定道具的消失、出现、
    位置或状态跳变。不得因为通用修复建议中出现“道具状态”几个字，
    把人物位置或姿态冲突改成道具连续性。
32. 已明确使用SEMANTIC_STATE_CONTINUITY或SEMANTIC_IDENTITY_CONTINUITY的问题，
    除非标题、正文和证据都明确聚焦固定道具，否则不得重分类。
33. rule_id已经是SEMANTIC_STATE_CONTINUITY时，不得因为path位于
    generation_segments、video_prompt或first_frame_prompt而把它视为分段问题。
34. 对同一镜头边界只返回一条SEMANTIC_STATE_CONTINUITY。
    “与上述相同、不再重复列出、同前述冲突”等引用型附属说明不得作为独立issue。
35. 同一状态根因在opening_state、first_frame_prompt、video_prompt和
    generation_segments中重复出现时，应在一条issue中合并证据，不得按字段扣分。
36. SEMANTIC_EVENT_ORDER只检查facts.required_events彼此之间的相对先后顺序。
    固定事件之前、之间或之后出现其他动作，不代表固定事件顺序错误。
37. 额外动作过多、节奏无法完成时，只报告SEMANTIC_ACTION_FEASIBILITY。
    不得再把相同额外动作解释为“可能改变事件顺序”并重复扣分。
38. 当message或evidence已经确认“符合顺序、顺序正确、先后关系正确”时，
    不得返回SEMANTIC_EVENT_ORDER。
39. 事件顺序错误必须给出至少两个固定事件，并明确说明实际先后与facts要求相反。
    “可能改变、可能影响、额外动作不在facts中”不能作为顺序错误证据。
40. opening_state描述镜头开始瞬间，action_path描述镜头开始之后发生的动作。
    如果上一镜ending_state与当前镜opening_state一致，则action_path随后收回手、
    站起、转身、走动或改变姿态是正常时间推进，不是跨镜头连续性冲突。
41. 不得要求opening_state提前写入action_path随后才会发生的变化。
    例如opening_state写“手按桌面”，action_path第一步写“收回手”，完全合法。
42. SEMANTIC_STATE_CONTINUITY必须证明上一镜ending_state与当前镜opening_state
    本身不一致。若二者一致，不得使用该rule_id。
43. 极短镜头内包含大量完整位移、取放物件、往返和姿态变化时，
    使用SEMANTIC_ACTION_FEASIBILITY，不得改报状态连续性。
44. facts.required_events的精确短语全部存在但相对顺序错误时，
    使用SEMANTIC_EVENT_ORDER。该问题可能已由确定性预检报告，
    hard_issues或已有语义问题中存在同镜头同规则时不得重复输出。
45. 固定事件顺序只比较事件短语在action_path或video_prompt中的实际出现位置，
    不得因语言风格、标点或其他额外动作而忽略明确逆序。
46. first_frame_prompt只描述镜头的第一个静止瞬间，video_prompt描述该瞬间之后
    展开的运动过程。首帧写“水杯仍在右侧、尚未移动”，video_prompt随后写
    “人物开始把水杯推向左侧”是合法时间推进，不是状态冲突。
47. 不得要求first_frame_prompt提前显示video_prompt后续动作已经完成的状态。
48. 当ending_state、opening_state和first_frame_prompt在镜头起点一致时，
    video_prompt随后发生人物动作、道具移动、姿态改变均不构成
    SEMANTIC_STATE_CONTINUITY。
49. 只有first_frame_prompt本身与opening_state矛盾，或video_prompt的动作起点
    与首帧已建立状态不一致时，才可报告首帧与视频提示词冲突。
50. SEMANTIC_ACTION_FEASIBILITY作为严重错误时，必须有明确的最低动作耗时、
    动作节点数量或物理限制证据，证明无法在镜头时长内完成。
51. “时间紧张、可能无法、可能来不及、存在风险、大概率无法”等推测措辞
    不能单独构成严重错误。
52. 如果分析中已承认某动作本身在时长内可行，且估算总耗时未明确超过镜头时长，
    不得返回SEMANTIC_ACTION_FEASIBILITY。
53. 简单连续动作可以使用镜头全部时长。灯光闪灭、切黑等瞬时画面事件
    不应被机械地各自追加完整动作耗时。
54. SEMANTIC_ACTION_FEASIBILITY严重错误由系统确定性预检负责。
    如果hard_issues或系统已有结果未报告该规则，不得仅凭主观节奏估算、
    自行假设的“至少1秒”或“明显超过”追加此错误。
55. 不得把“平稳”解释为“缓慢”，不得为未标注时长的简单动作任意分配
    最低耗时后据此扣分。
56. 对动作可行性只有建议性担忧但无确定性证据时，issues中不要输出。
57. 当上一镜ending_state与当前镜opening_state一致，但first_frame_prompt
    没有继承opening_state时，问题应定位到当前镜first_frame_prompt，
    不得错误声称opening_state与上一镜冲突。
58. 首帧冲突的title应为“首帧状态与开场状态冲突”，path应准确指向
    director_output.shots[n].first_frame_prompt。
59. evidence必须同时列出上一镜ending_state、当前镜opening_state和
    当前镜first_frame_prompt，并明确前两者一致、第三者发生跳变。
60. 不得在同一issue中先声称opening_state发生跳变，随后又承认
    opening_state与上一镜ending_state完全一致。
61. 已登记固定道具发生无依据消失、出现、位置变化或物理状态变化时，
    必须使用SEMANTIC_PROP_CONTINUITY。只写“信封”“水杯”等正式道具
    名称或简称，也足以确认变化主体，不要求出现“道具”二字。
62. 当变化主体是信封、水杯等固定道具时，不得使用
    SEMANTIC_STATE_CONTINUITY代替SEMANTIC_PROP_CONTINUITY。
63. 固定道具跨镜头问题应定位到发生变化的当前镜opening_state，
    不得错误定位到当前镜ending_state。
64. 人物仅作为道具位置参照，例如“陈默左手前方”，不代表人物状态变化。

不要因为正常的服装变化、发丝运动、表情变化或光线变化误报人物换人。
只报告有明确证据且最终确认成立的问题。

输出合法JSON：
{
  "issues": [
    {
      "rule_id": "SEMANTIC_X",
      "severity": "error",
      "title": "",
      "message": "",
      "path": "",
      "evidence": "",
      "suggestion": ""
    }
  ]
}

无问题时输出：
{"issues":[]}

禁止输出Markdown、说明文字或完整改写方案。
""".strip()

    user = json.dumps(
        {
            "facts": facts.model_dump(),
            "director_output": output.model_dump(),
            "hard_issues": [
                issue.model_dump()
                for issue in (hard_issues or [])
            ],
        },
        ensure_ascii=False,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        max_tokens=5000,
        temperature=0,
        extra_body={"thinking": {"type": "disabled"}},
        stream=False,
    )

    content = response.choices[0].message.content or ""
    if not content.strip():
        raise RuntimeError("DeepSeek返回空内容")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "DeepSeek语义审计返回了无法解析的JSON"
        ) from exc

    validated_llm_issues = [
        Issue.model_validate(item)
        for item in parsed.get("issues", [])
    ]

    llm_issues: list[Issue] = []
    for issue in validated_llm_issues:
        if (
            (
                str(_field_value(issue, "rule_id", "")).upper()
                not in CONTINUITY_RULE_IDS
                and _is_self_negated_issue(issue)
            )
            or _is_false_event_order_issue(
                issue,
                facts,
                output,
            )
            or _is_false_same_shot_progression_issue(
                issue,
                output,
            )
            or _is_speculative_action_feasibility_issue(
                issue,
                output,
            )
        ):
            continue

        family_validated_issue = _validate_semantic_issue_family(
            issue,
            facts,
            output,
        )
        if family_validated_issue is None:
            continue

        order_validated_issue = _validate_event_order_issue_family(
            family_validated_issue,
            facts,
            output,
        )
        if order_validated_issue is None:
            continue

        identity_validated_issue = _validate_identity_issue_family(
            order_validated_issue,
            facts,
            output,
        )
        if identity_validated_issue is None:
            continue

        if _is_semantic_issue_covered_by_hard_rules(
            identity_validated_issue,
            hard_issues or [],
            facts,
            output,
        ):
            continue

        if _is_false_same_shot_prop_progression_issue(
            identity_validated_issue,
            facts,
            output,
        ):
            continue

        if _is_false_continuity_issue_for_explicit_transition(
            identity_validated_issue,
            facts,
            output,
        ):
            continue

        canonical_issue = _canonicalize_semantic_issue(
            identity_validated_issue,
            facts,
            output,
        )
        # Continuity-only validity checks must see the final normalized rule.
        # A raw continuity label can be reclassified by the family validators,
        # so filtering it earlier can accidentally discard a valid non-
        # continuity finding such as event-order evidence.
        if not _semantic_continuity_issue_has_explicit_source_conflict(
            canonical_issue,
            facts,
            output,
        ):
            continue

        if (
            _is_self_negated_issue(canonical_issue)
            or _semantic_issue_explicitly_denies_continuity_conflict(
                canonical_issue
            )
            or _semantic_issue_is_omission_only_continuity_claim(
                canonical_issue
            )
        ):
            continue

        llm_issues.append(canonical_issue)



    # Dialogue/unknown-character hard rules own speaker and line attribution
    # errors. Keep identity only when its own text has visual replacement proof.
    llm_issues = [
        issue
        for issue in llm_issues
        if not _is_duplicate_identity_of_hard_issue(
            issue,
            hard_issues or [],
            output,
        )
    ]

    deterministic_event_order_shots = {
        _shot_id_from_issue(issue, output)
        for issue in deterministic_issues
        if issue.rule_id == "SEMANTIC_EVENT_ORDER"
    }
    deterministic_event_order_shots.discard("")

    if deterministic_event_order_shots:
        llm_issues = [
            issue
            for issue in llm_issues
            if not (
                _issue_family(issue) == "event_order"
                and _shot_id_from_issue(
                    issue,
                    output,
                ) in deterministic_event_order_shots
            )
        ]

    deterministic_action_shots = {
        _shot_id_from_issue(issue, output)
        for issue in deterministic_issues
        if (
            issue.rule_id
            == "SEMANTIC_ACTION_FEASIBILITY"
        )
    }
    deterministic_action_shots.discard("")

    # 动作可行性严重错误以确定性预检为唯一裁决来源。
    llm_issues = [
        issue
        for issue in llm_issues
        if not _is_unconfirmed_llm_action_feasibility_issue(
            issue,
            deterministic_action_shots,
            output,
        )
    ]

    if deterministic_action_shots:
        llm_issues = [
            issue
            for issue in llm_issues
            if not (
                _issue_family(issue)
                == "action_feasibility"
                and _shot_id_from_issue(
                    issue,
                    output,
                ) in deterministic_action_shots
            )
        ]

    # 避免确定性预检与DeepSeek对同一身份错误重复计分。
    existing_identity_error = any(
        issue.rule_id == "SEMANTIC_IDENTITY_CONTINUITY"
        for issue in deterministic_issues
    )

    if existing_identity_error:
        llm_issues = [
            issue
            for issue in llm_issues
            if not (
                "身份" in issue.title
                or "换人" in issue.message
                or "另一名" in issue.message
                or "五官" in issue.message
            )
        ]

    semantic_issues = deterministic_issues + llm_issues

    return _filter_and_group_semantic_issues(
        hard_issues or [],
        semantic_issues,
        output,
        facts,
    )
