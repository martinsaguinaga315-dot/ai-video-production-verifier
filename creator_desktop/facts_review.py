from __future__ import annotations

import json

import customtkinter as ctk
from pydantic import ValidationError

from models import DialogueLine, ProjectFacts


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def apply_facts_edits(facts: ProjectFacts, edits: dict) -> ProjectFacts:
    """Rebuild ProjectFacts after user corrections; no silent coercion."""
    data = facts.model_dump(mode="json")
    data["title"] = edits["title"].strip()
    data["total_duration"] = float(edits["total_duration"])
    renamed: dict[str, str] = {}
    for index, value in enumerate(edits["character_ids"]):
        old = data["characters"][index]["character_id"]
        new = value.strip()
        renamed[old] = new
        data["characters"][index]["character_id"] = new
    for prop in data["props"]:
        if prop.get("owner") in renamed:
            prop["owner"] = renamed[prop["owner"]]
    for index, shot_edit in enumerate(edits["shots"]):
        shot = data["shots"][index]
        shot["required_events"] = _split_lines(shot_edit["required_events"])
        shot["forbidden_events"] = _split_lines(shot_edit["forbidden_events"])
        dialogue = []
        for line in _split_lines(shot_edit["dialogue"]):
            if "：" in line:
                speaker, text = line.split("：", 1)
            elif ":" in line:
                speaker, text = line.split(":", 1)
            else:
                raise ValueError("精确台词每行需使用“人物：台词”格式。")
            dialogue.append(DialogueLine(speaker=speaker.strip(), text=text.strip()).model_dump())
        shot["exact_dialogue"] = dialogue
    return ProjectFacts.model_validate(data)


class FactsReviewFrame(ctk.CTkFrame):
    def __init__(self, master, facts: ProjectFacts, on_confirm, on_back, on_retry, on_json) -> None:
        super().__init__(master)
        self._facts, self._on_confirm = facts, on_confirm
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="确认项目事实", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=20, pady=(18, 4), anchor="w")
        ctk.CTkLabel(self, text="请确认这些内容是项目中不可被导演方案随意修改的事实。自动提取可能遗漏，请重点检查人物、道具、台词和时间线。", wraplength=850, justify="left").pack(padx=20, pady=(0, 10), anchor="w")
        self.body = ctk.CTkScrollableFrame(self, label_text="事实草稿")
        self.body.pack(fill="both", expand=True, padx=20, pady=8)
        self.title_var = ctk.StringVar(value=facts.title)
        self.duration_var = ctk.StringVar(value=str(facts.total_duration))
        self.character_vars = [ctk.StringVar(value=item.character_id) for item in facts.characters]
        self.shot_widgets = []
        self._build_fields()
        self.error_var = ctk.StringVar()
        ctk.CTkLabel(self, textvariable=self.error_var, text_color="#b22222", anchor="w").pack(padx=20, anchor="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=12)
        ctk.CTkButton(buttons, text="确认事实并继续", command=self._confirm).pack(side="left")
        ctk.CTkButton(buttons, text="返回修改原文", command=on_back).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="重新提取", command=on_retry).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="查看专业JSON", command=on_json).pack(side="right")

    def _entry(self, label: str, variable) -> None:
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(row, text=label, width=120, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=variable).pack(side="left", fill="x", expand=True)

    def _build_fields(self) -> None:
        self._entry("项目标题", self.title_var)
        self._entry("总时长（秒）", self.duration_var)
        for index, variable in enumerate(self.character_vars):
            self._entry(f"人物 {index + 1}", variable)
        for shot in self._facts.shots:
            frame = ctk.CTkFrame(self.body)
            frame.pack(fill="x", padx=8, pady=8)
            ctk.CTkLabel(frame, text=f"{shot.shot_id}｜{shot.start_time}-{shot.end_time}秒", font=ctk.CTkFont(weight="bold")).pack(padx=8, pady=5, anchor="w")
            req, forbidden, dialogue = ctk.CTkTextbox(frame, height=58), ctk.CTkTextbox(frame, height=50), ctk.CTkTextbox(frame, height=58)
            for label, box, value in (("必须事件（每行一项）", req, "\n".join(shot.required_events)), ("禁止事件（每行一项）", forbidden, "\n".join(shot.forbidden_events)), ("精确台词（人物：台词）", dialogue, "\n".join(f"{x.speaker}：{x.text}" for x in shot.exact_dialogue))):
                ctk.CTkLabel(frame, text=label).pack(padx=8, anchor="w")
                box.pack(fill="x", padx=8, pady=(0, 5))
                box.insert("1.0", value)
            self.shot_widgets.append((req, forbidden, dialogue))

    def _confirm(self) -> None:
        try:
            edits = {"title": self.title_var.get(), "total_duration": self.duration_var.get(), "character_ids": [x.get() for x in self.character_vars], "shots": [{"required_events": a.get("1.0", "end"), "forbidden_events": b.get("1.0", "end"), "dialogue": c.get("1.0", "end")} for a, b, c in self.shot_widgets]}
            self._on_confirm(apply_facts_edits(self._facts, edits))
        except (ValueError, ValidationError) as exc:
            self.error_var.set("事实修改无效，请检查时长、人物名称和台词格式。")


def show_json_dialog(master, value) -> None:
    dialog = ctk.CTkToplevel(master)
    dialog.title("专业JSON")
    dialog.geometry("760x560")
    box = ctk.CTkTextbox(dialog)
    box.pack(fill="both", expand=True, padx=12, pady=12)
    box.insert("1.0", json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2))
    box.configure(state="disabled")
