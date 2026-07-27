from __future__ import annotations
import json, math, re
from collections import Counter
from typing import Any
from models import DirectorOutput, Issue, ProjectFacts, VerificationReport

MOTION_WORDS = ("冲入","跑出","转身","转动","后仰","坠落","掉落","迈步","举枪","下沉","冲向","伸手","说出","开口","回头")

def norm(text: str) -> str:
    return re.sub(r"[\s，。、“”‘’：:；;！!？?…·\-—_（）()\[\]【】]", "", text or "")


def field_value(value: Any, field_name: str, default: Any = None) -> Any:
    """兼容Pydantic模型、普通对象和dict。"""
    if isinstance(value, dict):
        return value.get(field_name, default)
    return getattr(value, field_name, default)


# “事实层事件”与常见导演表达之间的同义映射。
# 每个外层列表代表一种可接受写法；内层多个词必须同时出现。
REQUIRED_EVENT_PATTERNS: dict[str, list[list[str]]] = {
    "A冲上天台": [
        ["A冲上天台"],
        ["A冲入天台"],
        ["A", "冲入天台"],
    ],
    "跑出几步后停住": [
        ["跑出几步后停住"],
        ["疾跑几步", "停住"],
        ["跑动几步", "停住"],
        ["向前跑出几步", "停住"],
    ],
    "缓慢抬起手枪": [
        ["缓慢抬起手枪"],
        ["缓慢", "枪口举起"],
        ["缓慢举枪"],
    ],
    "B背对A": [
        ["B背对A"],
        ["B", "背对镜头"],
        ["B", "背影"],
    ],
    "枪口轻微晃动": [
        ["枪口轻微晃动"],
        ["枪口", "极小", "轻微", "晃动"],
        ["枪口", "轻微", "无规律", "晃动"],
    ],
    "B从背对开始": [
        ["B从背对开始"],
        ["B", "背对镜头"],
        ["初始画面", "B背对"],
    ],
    "缓慢回头": [
        ["缓慢回头"],
        ["缓慢", "转动头部"],
        ["极其缓慢", "转头"],
        ["头部开始", "向A", "转动"],
    ],
    "看清A": [
        ["看清A"],
        ["视线", "锁定在A脸上"],
        ["视线", "落在A身上"],
        ["看向A"],
    ],
    "A冲向B": [
        ["A冲向B"],
        ["A", "爆发式", "冲向B"],
        ["A", "向前冲出"],
    ],
    "B正面对A后仰": [
        ["B正面对A后仰"],
        ["正面对A", "向后仰"],
        ["保持正面对A", "后仰"],
        ["面向A", "向后倒"],
    ],
    "A没有碰到B": [
        ["A没有碰到B"],
        ["绝对无法触及"],
        ["绝对不能碰到B"],
        ["不能碰到B"],
        ["无法触及B"],
    ],
}

def contains_required_event(normalized_text: str, event: str) -> bool:
    """优先匹配同义模式；再进行保守的动作词规范化匹配。"""
    alternatives = REQUIRED_EVENT_PATTERNS.get(event, [[event]])
    if any(
        all(norm(part) in normalized_text for part in alternative)
        for alternative in alternatives
    ):
        return True

    canonical_event = norm(event)
    canonical_text = normalized_text

    replacements = {
        "急促跑出几步后突然停住": "跑几步停住",
        "急促跑出几步": "跑几步",
        "跑出几步": "跑几步",
        "冲上天台": "冲天台",
        "冲入天台": "冲天台",
        "向前冲去": "冲去",
        "猛地向前冲去": "冲去",
        "缓慢转动头部": "缓慢转头",
        "转动头部": "转头",
        "嘴角出现极轻的微笑": "嘴角出现轻微笑意",
        "极轻的微笑": "轻微笑意",
        "极轻微笑": "轻微笑意",
        "笑意只停留一瞬后缓慢消失": "笑意消失",
        "右手自然垂在身侧握打火机": "右手握打火机",
        "右手握着打火机": "右手握打火机",
        "右手缓慢松开": "右手松开",
        "手指距离B的手只差一点但没有碰到": "没有碰到B",
        "手指距离B的手只差一点但没有碰到": "没有碰到B",
        "未回头": "不回头",
        "没有回头": "不回头",
    }
    for source, target in replacements.items():
        canonical_event = canonical_event.replace(norm(source), norm(target))
        canonical_text = canonical_text.replace(norm(source), norm(target))

    return canonical_event in canonical_text

NEGATION_MARKERS = (
    "无", "没有", "未", "不", "不会", "不能", "不可", "不得",
    "禁止", "严禁", "避免", "杜绝", "不允许", "不应",
)

def contains_affirmative_term(normalized_text: str, term: str) -> bool:
    """只有关键词以肯定语义出现时才返回True，忽略“禁止出现/没有/不得”等否定表达。"""
    target = norm(term)
    if not target:
        return False

    start = 0
    while True:
        index = normalized_text.find(target, start)
        if index < 0:
            return False

        # 查看关键词前最多12个规范化字符，判断是否被否定词控制
        prefix = normalized_text[max(0, index - 12):index]
        negated = any(marker in prefix for marker in NEGATION_MARKERS)

        if not negated:
            return True

        start = index + len(target)


FORBIDDEN_ACTION_VERBS = (
    "发生身体接触",
    "身体接触",
    "提前走到",
    "提前走向",
    "自动移动",
    "变成其他物品",
    "触碰",
    "接触",
    "拿起",
    "推动",
    "打开",
    "撕破",
    "拆封",
    "被替换",
    "替换",
    "走向",
    "走到",
    "说话",
    "喊叫",
    "哭泣",
    "争吵",
    "拥抱",
    "打斗",
    "移动",
)


def _action_is_negated(
    normalized_text: str,
    action_index: int,
) -> bool:
    prefix = normalized_text[
        max(0, action_index - 12):action_index
    ]
    return any(
        marker in prefix
        for marker in NEGATION_MARKERS
    )


def _split_forbidden_event(
    event: str,
) -> tuple[str, str, str] | None:
    """
    将明确动作禁令拆为“主体 + 动作 + 对象”。

    例如：
    陈默触碰信封
    -> 陈默 / 触碰 / 信封

    林夏提前走到桌边
    -> 林夏 / 提前走到 / 桌边
    """
    target = norm(event)
    if not target:
        return None

    for action in sorted(
        FORBIDDEN_ACTION_VERBS,
        key=len,
        reverse=True,
    ):
        normalized_action = norm(action)
        index = target.find(normalized_action)
        if index < 0:
            continue

        subject = target[:index]
        obj = target[index + len(normalized_action):]

        if not subject:
            continue

        return subject, normalized_action, obj

    return None


def contains_forbidden_event(
    normalized_text: str,
    event: str,
) -> bool:
    """
    检测镜头中是否肯定发生了禁用动作。

    第一层仍使用完整短语匹配。
    第二层允许主体和动作之间插入手部、姿态、速度等修饰语，
    但要求主体、动作、对象按顺序在有限距离内出现。

    示例：
    禁令“陈默触碰信封”
    可以识别“陈默伸出右手触碰信封”。
    """
    if contains_affirmative_term(normalized_text, event):
        return True

    parts = _split_forbidden_event(event)
    if parts is None:
        return False

    subject, action, obj = parts
    subject_start = 0

    while True:
        subject_index = normalized_text.find(
            subject,
            subject_start,
        )
        if subject_index < 0:
            return False

        subject_end = subject_index + len(subject)

        # 主体与动作之间允许插入少量动作修饰，
        # 但不能跨越过长文本误连到另一事件。
        action_search_end = min(
            len(normalized_text),
            subject_end + 24,
        )
        action_index = normalized_text.find(
            action,
            subject_end,
            action_search_end,
        )

        if (
            action_index >= 0
            and not _action_is_negated(
                normalized_text,
                action_index,
            )
        ):
            if not obj:
                return True

            action_end = action_index + len(action)
            object_search_end = min(
                len(normalized_text),
                action_end + 18,
            )
            object_index = normalized_text.find(
                obj,
                action_end,
                object_search_end,
            )
            if object_index >= 0:
                return True

        subject_start = subject_index + len(subject)



def _parse_before_shot_constraint(
    term: str,
) -> tuple[str, str, str] | None:
    """
    解析“人物在S04之前执行某动作”类型的跨镜头禁令。

    示例：
    林夏在S04之前走到餐桌旁
    -> 林夏 / S04 / 走到餐桌旁

    陈默在S05之前触碰信封
    -> 陈默 / S05 / 触碰信封
    """
    value = str(term or "").strip()
    value = re.sub(
        r"^(禁止|不得|不能|不允许)",
        "",
        value,
    ).strip()

    match = re.match(
        r"^(.+?)在(S\d+)之前(.+)$",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    subject = match.group(1).strip()
    boundary_shot_id = match.group(2).upper()
    action_and_object = match.group(3).strip()

    if not subject or not action_and_object:
        return None

    return subject, boundary_shot_id, action_and_object


def _issue_already_covers_event(
    issues: list[Issue],
    shot_id: str,
    event: str,
) -> bool:
    """
    避免同一事件同时被镜头级FORBIDDEN_EVENT与时间边界规则重复扣分。
    """
    event_key = norm(event)
    expected_path = f"shots.{shot_id}"

    for existing in issues:
        if existing.severity != "error":
            continue
        if existing.path != expected_path:
            continue

        combined = norm(
            f"{existing.message}{existing.evidence}"
        )
        if event_key and event_key in combined:
            return True

    return False


def _check_before_shot_constraints(
    facts: ProjectFacts,
    actual: dict[str, Any],
    positive_text_by_shot: dict[str, str],
    issues: list[Issue],
) -> None:
    """
    检查“在某镜头之前不得发生”的跨镜头时间边界约束。

    边界顺序以facts中的锁定时间轴为准，避免导演输出擅自改时间后
    反过来绕过规则。
    """
    ordered_fact_shots = sorted(
        facts.shots,
        key=lambda item: (
            item.start_time,
            item.end_time,
            item.shot_id,
        ),
    )
    order = {
        shot.shot_id: index
        for index, shot in enumerate(ordered_fact_shots)
    }

    for term in facts.global_forbidden_events:
        parsed = _parse_before_shot_constraint(term)
        if parsed is None:
            continue

        subject, boundary_shot_id, action_and_object = parsed
        boundary_index = order.get(boundary_shot_id)
        if boundary_index is None:
            continue

        event = f"{subject}{action_and_object}"

        for fact_shot in ordered_fact_shots[:boundary_index]:
            shot_id = fact_shot.shot_id
            if shot_id not in actual:
                continue

            shot_text = positive_text_by_shot.get(
                shot_id,
                "",
            )
            if not contains_forbidden_event(
                shot_text,
                event,
            ):
                continue

            if _issue_already_covers_event(
                issues,
                shot_id,
                event,
            ):
                continue

            issues.append(issue(
                "EVENT_TOO_EARLY",
                "error",
                "事件早于允许镜头发生",
                (
                    f"{shot_id}在{boundary_shot_id}之前出现："
                    f"{event}"
                ),
                f"shots.{shot_id}",
                evidence=term,
                suggestion=(
                    f"从{shot_id}删除该动作，"
                    f"最早只能从{boundary_shot_id}开始发生。"
                ),
            ))



def shot_positive_text(shot: Any) -> str:
    """只汇总镜头中描述真实发生内容的字段，不读取negative_constraints。"""
    payload = {
        "opening_state": shot.opening_state,
        "action_path": shot.action_path,
        "performance": shot.performance,
        "dialogue": [
            {"speaker": item.speaker, "text": item.text}
            for item in shot.dialogue
        ],
        "sound": shot.sound,
        "ending_state": shot.ending_state,
        "video_prompt": shot.video_prompt,
        "segments": [
            {
                "video_prompt": seg.video_prompt,
            }
            for seg in shot.generation_segments
        ],
    }
    return norm(dump(payload))


def output_positive_text(output: Any) -> str:
    """
    汇总真实发生或真实存在的内容。

    只读取可进入最终画面的肯定描述，排除：
    - negative_constraints
    - project中的创作原则
    - props.important_note等约束说明
    - props.cross_shot_consistency等制作备注

    道具卡的important_note通常会集中列出“禁止打开、消失、替换”等词。
    这些词是约束元数据，不代表画面中真的发生了对应行为。
    """
    positive_props = [
        {
            "prop_id": field_value(prop, "prop_id", ""),
            "name": field_value(prop, "name", ""),
            "owner": field_value(prop, "owner", ""),
            "appearance_and_material": field_value(
                prop,
                "appearance_and_material",
                "",
            ),
        }
        for prop in output.props
    ]

    payload = {
        "characters": output.characters,
        "locations": output.locations,
        "props": positive_props,
        "shots": [
            {
                "opening_state": shot.opening_state,
                "action_path": shot.action_path,
                "performance": shot.performance,
                "dialogue": [
                    {"speaker": d.speaker, "text": d.text}
                    for d in shot.dialogue
                ],
                "sound": shot.sound,
                "ending_state": shot.ending_state,
                "first_frame_prompt": shot.first_frame_prompt,
                "video_prompt": shot.video_prompt,
                "segments": [
                    {
                        "first_frame_prompt": seg.first_frame_prompt,
                        "video_prompt": seg.video_prompt,
                    }
                    for seg in shot.generation_segments
                ],
            }
            for shot in output.shots
        ],
    }
    return norm(dump(payload))


def location_positive_text(output: Any) -> str:
    """场景物理检查只读取地点的肯定描述，避免把禁止句当成真实结构。"""
    return norm(dump(output.locations))


def _json_default(value: Any) -> Any:
    """递归处理嵌套的Pydantic模型和集合类型。"""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, set):
        return list(value)
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


def dump(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        default=_json_default,
    )

def issue(rule_id, severity, title, message, path="", evidence="", suggestion=""):
    return Issue(
        rule_id=rule_id, severity=severity, title=title, message=message,
        path=path, evidence=evidence[:500], suggestion=suggestion
    )

def verify(facts: ProjectFacts, output: DirectorOutput) -> VerificationReport:
    issues: list[Issue] = []
    shots = sorted(output.shots, key=lambda x: (x.start_time, x.shot_id))
    expected = {x.shot_id: x for x in facts.shots}
    actual = {x.shot_id: x for x in shots}
    positive_text_by_shot = {
        shot.shot_id: shot_positive_text(shot)
        for shot in shots
    }
    eps = 0.02

    # 结构与时间轴
    if len(shots) != facts.shot_count:
        issues.append(issue("SHOT_COUNT","error","镜头数量错误",
            f"要求{facts.shot_count}个，实际{len(shots)}个。","shots"))
    duplicate_ids = [k for k,v in Counter(s.shot_id for s in shots).items() if v > 1]
    if duplicate_ids:
        issues.append(issue("DUPLICATE_ID","error","镜头编号重复",",".join(duplicate_ids),"shots"))

    for i, shot in enumerate(shots):
        calculated = shot.end_time - shot.start_time
        if not math.isclose(calculated, shot.final_duration, abs_tol=eps):
            issues.append(issue("DURATION_MISMATCH","error","镜头时长字段不一致",
                f"{shot.shot_id}: end-start={calculated:.2f}s，final_duration={shot.final_duration:.2f}s。",
                f"shots.{shot.shot_id}"))
        if i:
            prev = shots[i-1]
            if shot.start_time > prev.end_time + eps:
                issues.append(issue("TIME_GAP","error","时间轴存在空档",
                    f"{prev.shot_id}结束{prev.end_time}s，{shot.shot_id}开始{shot.start_time}s。","shots"))
            if shot.start_time < prev.end_time - eps:
                issues.append(issue("TIME_OVERLAP","error","时间轴存在重叠",
                    f"{prev.shot_id}结束{prev.end_time}s，{shot.shot_id}开始{shot.start_time}s。","shots"))
    if shots and not math.isclose(shots[-1].end_time - shots[0].start_time, facts.total_duration, abs_tol=eps):
        issues.append(issue("TOTAL_DURATION","error","总时长不正确",
            f"要求{facts.total_duration}s，输出覆盖{shots[-1].end_time - shots[0].start_time}s。","shots"))

    # 未授权人物与道具
    allowed_character_ids = {
        norm(field_value(character, "character_id", ""))
        for character in facts.characters
        if norm(field_value(character, "character_id", ""))
    }
    allowed_prop_ids = {
        norm(field_value(prop, "prop_id", ""))
        for prop in facts.props
        if norm(field_value(prop, "prop_id", ""))
    }

    unknown_characters: dict[str, dict[str, Any]] = {}

    def register_unknown_character(
        character_id: str,
        path: str,
        location_label: str,
    ) -> None:
        normalized_id = norm(character_id)
        if not normalized_id or normalized_id in allowed_character_ids:
            return

        record = unknown_characters.setdefault(
            normalized_id,
            {
                "display": character_id,
                "paths": [],
                "locations": [],
            },
        )
        record["paths"].append(path)
        record["locations"].append(location_label)

    for index, character in enumerate(output.characters):
        register_unknown_character(
            str(field_value(character, "character_id", "")),
            f"characters[{index}].character_id",
            "人物卡",
        )

    for shot in shots:
        for index, character_id in enumerate(shot.characters):
            register_unknown_character(
                character_id,
                f"shots.{shot.shot_id}.characters[{index}]",
                shot.shot_id,
            )

    for record in unknown_characters.values():
        unique_locations = list(dict.fromkeys(record["locations"]))
        unique_paths = list(dict.fromkeys(record["paths"]))
        location_text = "、".join(unique_locations)

        issues.append(issue(
            "UNKNOWN_CHARACTER",
            "error",
            "出现事实层未定义人物",
            (
                f"导演输出擅自增加人物“{record['display']}”"
                f"（出现位置：{location_text}）。"
            ),
            unique_paths[0],
            evidence="；".join(unique_paths),
            suggestion=(
                "删除该人物；若剧本确实需要此人物，"
                "先在facts.characters中正式定义，再重新生成导演方案。"
            ),
        ))

    unknown_props: dict[str, dict[str, Any]] = {}

    def register_unknown_prop(
        prop_id: str,
        path: str,
        location_label: str,
    ) -> None:
        normalized_id = norm(prop_id)
        if not normalized_id or normalized_id in allowed_prop_ids:
            return

        record = unknown_props.setdefault(
            normalized_id,
            {
                "display": prop_id,
                "paths": [],
                "locations": [],
            },
        )
        record["paths"].append(path)
        record["locations"].append(location_label)

    for index, prop in enumerate(output.props):
        register_unknown_prop(
            str(field_value(prop, "prop_id", "")),
            f"props[{index}].prop_id",
            "道具卡",
        )

    for character_index, character in enumerate(output.characters):
        fixed_props = field_value(character, "fixed_props", []) or []
        character_id = str(
            field_value(character, "character_id", "")
        )

        for prop_index, prop_id in enumerate(fixed_props):
            register_unknown_prop(
                str(prop_id),
                (
                    f"characters[{character_index}]"
                    f".fixed_props[{prop_index}]"
                ),
                f"人物卡:{character_id}",
            )

    for record in unknown_props.values():
        unique_locations = list(dict.fromkeys(record["locations"]))
        unique_paths = list(dict.fromkeys(record["paths"]))
        location_text = "、".join(unique_locations)

        issues.append(issue(
            "UNKNOWN_PROP",
            "error",
            "出现事实层未定义道具",
            (
                f"导演输出擅自增加道具“{record['display']}”"
                f"（出现位置：{location_text}）。"
            ),
            unique_paths[0],
            evidence="；".join(unique_paths),
            suggestion=(
                "删除该道具；若剧本确实需要此道具，"
                "先在facts.props中正式定义，再重新生成导演方案。"
            ),
        ))

    # 固定镜头边界、事件、台词
    for shot_id, exp in expected.items():
        shot = actual.get(shot_id)
        if not shot:
            issues.append(issue("MISSING_SHOT","error","缺少固定镜头",shot_id,f"shots.{shot_id}"))
            continue
        if not (math.isclose(shot.start_time, exp.start_time, abs_tol=eps) and
                math.isclose(shot.end_time, exp.end_time, abs_tol=eps)):
            issues.append(issue("LOCKED_TIME","error","固定镜头时间被改变",
                f"{shot_id}应为{exp.start_time}-{exp.end_time}s，实际{shot.start_time}-{shot.end_time}s。",
                f"shots.{shot_id}"))

        shot_text = positive_text_by_shot.get(
            shot_id,
            shot_positive_text(shot),
        )

        for event in exp.required_events:
            if contains_required_event(shot_text, event):
                continue

            wrong_shots = [
                other_shot_id
                for other_shot_id, other_text in positive_text_by_shot.items()
                if (
                    other_shot_id != shot_id
                    and contains_required_event(other_text, event)
                )
            ]

            if wrong_shots:
                actual_location = "、".join(wrong_shots)
                issues.append(issue(
                    "EVENT_WRONG_SHOT",
                    "error",
                    "固定事件出现在错误镜头",
                    (
                        f"“{event}”应出现在{shot_id}，"
                        f"实际出现在{actual_location}。"
                    ),
                    f"shots.{wrong_shots[0]}",
                    evidence=event,
                    suggestion=(
                        f"从{actual_location}删除该事件，"
                        f"并将其放回{shot_id}。"
                    ),
                ))
            else:
                issues.append(issue(
                    "MISSING_EVENT",
                    "error",
                    "缺少固定事件",
                    f"{shot_id}缺少：{event}",
                    f"shots.{shot_id}",
                    evidence=event,
                    suggestion=(
                        "把事件写进action_path、opening_state或ending_state。"
                    ),
                ))
        for event in exp.forbidden_events:
            if contains_forbidden_event(shot_text, event):
                issues.append(issue(
                    "FORBIDDEN_EVENT",
                    "error",
                    "事件提前或出现禁用内容",
                    f"{shot_id}出现：{event}",
                    f"shots.{shot_id}",
                    event,
                ))

        wanted = [(norm(x.speaker), norm(x.text)) for x in exp.exact_dialogue]
        got = [(norm(x.speaker), norm(x.text)) for x in shot.dialogue]
        if wanted != got:
            issues.append(issue("DIALOGUE_EXACT","error","台词或所属镜头错误",
                f"{shot_id}期望{[(x.speaker,x.text) for x in exp.exact_dialogue]}，实际{[(x.speaker,x.text) for x in shot.dialogue]}。",
                f"shots.{shot_id}.dialogue"))

        # 克制说话约3.5个汉字/秒，另留0.2秒起落气息
        chars = len(re.findall(r"[\u4e00-\u9fff]", "".join(x.text for x in shot.dialogue)))
        speech_time = chars / 3.5 + (0.2 if chars else 0)
        if speech_time > shot.final_duration:
            issues.append(issue("SPEECH_TOO_LONG","error","台词没有足够时间",
                f"{shot_id}台词估算需{speech_time:.2f}s，镜头只有{shot.final_duration:.2f}s。",
                f"shots.{shot_id}.dialogue"))
        elif chars and speech_time > shot.final_duration * 0.7:
            issues.append(issue("SPEECH_TIGHT","warning","台词挤占动作时间",
                f"{shot_id}台词约占镜头{speech_time/shot.final_duration:.0%}。",f"shots.{shot_id}.dialogue"))

    # 跨镜头时间边界禁令
    _check_before_shot_constraints(
        facts,
        actual,
        positive_text_by_shot,
        issues,
    )

    whole = dump(output)
    whole_n = output_positive_text(output)

    # 全局禁用内容与道具状态
    for term in facts.global_forbidden_events:
        if contains_affirmative_term(whole_n, term):
            issues.append(issue(
                "GLOBAL_FORBIDDEN", "error", "出现全片禁止内容",
                term, "director_output", term
            ))
    for prop in facts.props:
        for term in prop.forbidden_terms:
            if contains_affirmative_term(whole_n, term):
                issues.append(issue(
                    "PROP_STATE", "error", "道具状态错误",
                    f"{prop.prop_id}出现禁止内容：{term}",
                    "props/shots", term
                ))

    # 人物外观、开场状态与服装锁定
    cmap = {
        str(field_value(character, "character_id", "")): character
        for character in output.characters
    }

    first_shot_text = (
        positive_text_by_shot.get(shots[0].shot_id, "")
        if shots
        else ""
    )

    for lock in facts.characters:
        char = cmap.get(lock.character_id)
        if not char:
            issues.append(issue(
                "MISSING_CHARACTER",
                "error",
                "缺少人物卡",
                lock.character_id,
                f"characters.{lock.character_id}",
            ))
            continue

        character_text = norm(dump(char))
        character_and_opening_text = norm(
            dump(char) + first_shot_text
        )

        missing_appearance = [
            term
            for term in lock.fixed_appearance_terms
            if norm(term) not in character_text
        ]
        forbidden_appearance = [
            term
            for term in lock.forbidden_appearance_terms
            if contains_affirmative_term(character_text, term)
        ]
        missing_initial_state = [
            term
            for term in lock.initial_state_terms
            if norm(term) not in character_and_opening_text
        ]
        missing_costume = [
            term
            for term in lock.fixed_costume_terms
            if norm(term) not in character_text
        ]
        forbidden_costume = [
            term
            for term in lock.forbidden_costume_terms
            if contains_affirmative_term(character_text, term)
        ]

        if missing_appearance:
            issues.append(issue(
                "APPEARANCE_MISSING",
                "error",
                "固定人物外观未完整保留",
                (
                    f"{lock.character_id}缺少："
                    f"{','.join(missing_appearance)}"
                ),
                f"characters.{lock.character_id}",
                evidence=",".join(missing_appearance),
                suggestion=(
                    "将facts.characters中的fixed_appearance_terms"
                    "完整写入人物卡fixed_appearance或full_text。"
                ),
            ))

        if forbidden_appearance:
            issues.append(issue(
                "APPEARANCE_CHANGED",
                "error",
                "人物固定外观被改变",
                (
                    f"{lock.character_id}出现："
                    f"{','.join(forbidden_appearance)}"
                ),
                f"characters.{lock.character_id}",
                evidence=",".join(forbidden_appearance),
            ))

        if missing_initial_state:
            issues.append(issue(
                "INITIAL_STATE_MISSING",
                "error",
                "人物开场状态未完整保留",
                (
                    f"{lock.character_id}缺少："
                    f"{','.join(missing_initial_state)}"
                ),
                f"characters.{lock.character_id}/shots.{shots[0].shot_id if shots else 'S01'}",
                evidence=",".join(missing_initial_state),
                suggestion=(
                    "将initial_state_terms写入人物卡initial_state，"
                    "并在开场镜头的opening_state、action_path或首帧中明确出现。"
                ),
            ))

        if missing_costume:
            issues.append(issue(
                "COSTUME_MISSING",
                "error",
                "固定服装未完整保留",
                (
                    f"{lock.character_id}缺少："
                    f"{','.join(missing_costume)}"
                ),
                f"characters.{lock.character_id}",
            ))

        if forbidden_costume:
            issues.append(issue(
                "COSTUME_CHANGED",
                "error",
                "人物服装被改变",
                (
                    f"{lock.character_id}出现："
                    f"{','.join(forbidden_costume)}"
                ),
                f"characters.{lock.character_id}",
            ))

    # 道具归属锁定：owner为空时，导演输出也不得擅自断言归属
    output_prop_map = {
        norm(str(field_value(prop, "prop_id", ""))):
        (index, prop)
        for index, prop in enumerate(output.props)
        if norm(str(field_value(prop, "prop_id", "")))
    }

    for prop_lock in facts.props:
        match = output_prop_map.get(norm(prop_lock.prop_id))
        if match is None:
            continue

        prop_index, output_prop = match
        actual_owner = str(
            field_value(output_prop, "owner", "")
        ).strip()
        expected_owner = str(prop_lock.owner or "").strip()

        if expected_owner and norm(actual_owner) != norm(expected_owner):
            issues.append(issue(
                "PROP_OWNER_MISMATCH",
                "error",
                "道具归属与事实层不一致",
                (
                    f"{prop_lock.prop_id}应归属“{expected_owner}”，"
                    f"实际为“{actual_owner or '空'}”。"
                ),
                f"props[{prop_index}].owner",
                evidence=actual_owner,
                suggestion="将道具owner恢复为facts.json中的锁定值。",
            ))

        if not expected_owner and actual_owner:
            issues.append(issue(
                "PROP_OWNER_UNVERIFIED",
                "error",
                "擅自推断道具归属",
                (
                    f"facts未确认{prop_lock.prop_id}的owner，"
                    f"导演输出却写为“{actual_owner}”。"
                ),
                f"props[{prop_index}].owner",
                evidence=actual_owner,
                suggestion=(
                    "将owner设为空字符串；"
                    "只有原剧本明确归属时才能填写人物ID。"
                ),
            ))

    # 拆分片段存在性、完整性、名称唯一性与时长一致性
    for shot in shots:
        valid_segment_durations: list[float] = []

        if not shot.generation_segments:
            issues.append(issue(
                "SEGMENT_MISSING",
                "error",
                "镜头缺少生成分段",
                f"{shot.shot_id}未提供任何generation_segments。",
                f"shots.{shot.shot_id}.generation_segments",
                evidence="[]",
                suggestion=(
                    "至少添加一个生成分段，并填写name、"
                    "recommended_generation_duration、"
                    "first_frame_prompt和video_prompt。"
                ),
            ))
            continue

        seen_segment_names: dict[str, int] = {}

        for i, seg in enumerate(shot.generation_segments):
            missing = []
            segment_name = str(seg.name or "").strip()
            segment_label = segment_name or f"第{i + 1}个分段"

            if not segment_name:
                missing.append("name")
            else:
                normalized_name = segment_name.casefold()
                if normalized_name in seen_segment_names:
                    first_index = seen_segment_names[normalized_name]
                    issues.append(issue(
                        "SEGMENT_NAME_DUPLICATE",
                        "error",
                        "生成分段名称重复",
                        (
                            f"{shot.shot_id}的第{first_index + 1}个分段和"
                            f"第{i + 1}个分段名称均为“{segment_name}”。"
                        ),
                        f"shots.{shot.shot_id}.generation_segments[{i}].name",
                        evidence=segment_name,
                        suggestion="为同一镜头内的每个生成分段设置唯一名称。",
                    ))
                else:
                    seen_segment_names[normalized_name] = i
            if not seg.first_frame_prompt.strip():
                missing.append("first_frame_prompt")
            if not seg.video_prompt.strip():
                missing.append("video_prompt")
            if seg.recommended_generation_duration is None:
                missing.append("recommended_generation_duration")

            if missing:
                issues.append(issue(
                    "SEGMENT_INCOMPLETE",
                    "error",
                    "拆分片段字段不完整",
                    f"{shot.shot_id}/{segment_label}缺少：{','.join(missing)}",
                    f"shots.{shot.shot_id}.generation_segments[{i}]",
                    evidence=",".join(missing),
                    suggestion="补齐该生成分段的必填字段。",
                ))
                continue

            duration = float(seg.recommended_generation_duration)
            valid_segment_durations.append(duration)

            if duration <= 0:
                issues.append(issue(
                    "SEGMENT_DURATION_INVALID",
                    "error",
                    "生成分段时长无效",
                    f"{shot.shot_id}/{seg.name}的建议生成时长为{duration:.2f}s，必须大于0。",
                    f"shots.{shot.shot_id}.generation_segments[{i}].recommended_generation_duration",
                    evidence=str(duration),
                    suggestion="将该分段时长改为大于0的数值。",
                ))

        # 只有存在生成分段且每段都填写了时长时，才核对总和。
        if (
            shot.generation_segments
            and len(valid_segment_durations) == len(shot.generation_segments)
        ):
            segment_total = sum(valid_segment_durations)

            if not math.isclose(
                segment_total,
                shot.final_duration,
                abs_tol=eps,
            ):
                issues.append(issue(
                    "SEGMENT_DURATION_TOTAL",
                    "error",
                    "生成分段时长总和不一致",
                    (
                        f"{shot.shot_id}镜头时长为{shot.final_duration:.2f}s，"
                        f"生成分段合计为{segment_total:.2f}s。"
                    ),
                    f"shots.{shot.shot_id}.generation_segments",
                    evidence=(
                        f"final_duration={shot.final_duration:.2f}; "
                        f"segment_total={segment_total:.2f}"
                    ),
                    suggestion=(
                        "调整recommended_generation_duration，"
                        "使全部生成分段时长之和等于镜头final_duration。"
                    ),
                ))

    # 首帧不能写连续动作
    for shot in shots:
        found = [x for x in MOTION_WORDS if x in shot.first_frame_prompt]
        if found:
            issues.append(issue("FIRST_FRAME_MOTION","warning","首帧含连续动作",
                f"{shot.shot_id}出现：{','.join(found)}",f"shots.{shot.shot_id}.first_frame_prompt",
                suggestion="首帧只描述一个静止瞬间。"))
        for i, seg in enumerate(shot.generation_segments):
            found = [x for x in MOTION_WORDS if x in seg.first_frame_prompt]
            if found:
                issues.append(issue("SEGMENT_FIRST_FRAME_MOTION","warning","片段首帧含连续动作",
                    f"{shot.shot_id}/{seg.name}出现：{','.join(found)}",
                    f"shots.{shot.shot_id}.generation_segments[{i}].first_frame_prompt"))

    # 场景物理冲突：只读取地点的肯定描述，不扫描禁止约束。
    location_text = location_positive_text(output)
    action_text = norm(dump([
        {
            "action_path": shot.action_path,
            "ending_state": shot.ending_state,
            "video_prompt": shot.video_prompt,
        }
        for shot in output.shots
    ]))

    has_high_parapet = (
        contains_affirmative_term(location_text, "1.2米女儿墙")
        or (
            contains_affirmative_term(location_text, "1.2米")
            and contains_affirmative_term(location_text, "女儿墙")
        )
    )
    requires_edge_fall = (
        "后退半步" in action_text
        and ("坠落" in action_text or "坠出画面" in action_text)
    )
    if has_high_parapet and requires_edge_fall:
        issues.append(issue(
            "GEOMETRY_CONFLICT", "error", "场景几何与动作冲突",
            "存在约1.2米女儿墙，却要求后退半步直接坠落。",
            "locations/shots",
            suggestion="坠落位置应明确为开放边缘或低矮挡水坎。"
        ))

    has_railing = contains_affirmative_term(location_text, "金属护栏")
    if has_railing and "脚跟越过" in action_text and (
        "坠落" in action_text or "坠出画面" in action_text
    ):
        issues.append(issue(
            "RAILING_CONFLICT", "error", "护栏阻挡坠落动作",
            "坠落位置存在金属护栏，但动作要求脚跟越过边缘。",
            "locations/shots"
        ))
    if "缓慢" in whole and re.search(r"0\.?5\s*秒内完成", whole):
        issues.append(issue("SPEED_CONFLICT","error","动作速度互相冲突",
            "同时要求缓慢执行和0.5秒内完成。","shots"))

    # 黑屏声音是否额外延长总片长
    for shot in shots:
        m = re.search(r"黑(?:屏|暗)中.*?(\d+(?:\.\d+)?)\s*秒", dump(shot))
        if m and math.isclose(shot.end_time, facts.total_duration, abs_tol=eps):
            issues.append(issue("AUDIO_TAIL","warning","黑屏声音可能延长总片长",
                f"{shot.shot_id}描述黑屏声音约{m.group(1)}秒，请明确是否包含在15秒内。",
                f"shots.{shot.shot_id}"))

    errors = sum(x.severity == "error" for x in issues)
    warnings = sum(x.severity == "warning" for x in issues)
    return VerificationReport(
        passed=errors == 0,
        score=max(0, 100-errors*10-warnings*3),
        errors=errors,
        warnings=warnings,
        issues=issues
    )
