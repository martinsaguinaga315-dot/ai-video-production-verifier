"""Read-only result display for AI Creator storyboard generation."""
from __future__ import annotations

import json
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from story_generation.models import GenerationResult, StoryboardDraft
from creator_desktop.ui_components import PageTitle, PrimaryButton, SecondaryButton, SoftCard, StatusText
from creator_desktop.ui_theme import CARD_BACKGROUND, CARD_BORDER, MAIN_CONTENT_WIDE, PAGE_GUTTER, RADIUS_CARD, SUCCESS, TEXT_SECONDARY


class CreatorGenerationResultFrame(ctk.CTkFrame):
    """Render a GenerationResult without invoking any generation services."""

    def __init__(self, master, on_back=None) -> None:
        super().__init__(master, fg_color="transparent")
        self.rendered_text = ""
        self._result: GenerationResult | None = None
        self.shot_cards = []
        self.copy_status = ctk.StringVar(value="")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        main = ctk.CTkFrame(self, fg_color="transparent", width=MAIN_CONTENT_WIDE)
        main.grid(row=0, column=0, padx=PAGE_GUTTER, pady=(12, 18), sticky="nsew")
        main.grid_columnconfigure(0, weight=1); main.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, pady=(10, 14), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        PageTitle(titles, text="Storyboard 生成结果").pack(anchor="w")
        ctk.CTkLabel(titles, text="查看镜头、提示词和制片规则核验结果", text_color=TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))
        SecondaryButton(header, text="返回 AI 创作", width=128, command=on_back).grid(row=0, column=1, sticky="e")
        self.content = ctk.CTkScrollableFrame(main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.clear()

    def clear(self) -> None:
        self._result = None
        self._clear_content()
        self.show_message("等待 Storyboard 生成结果。")

    def show_message(self, message: str) -> None:
        self._clear_content()
        self.rendered_text = message
        card = SoftCard(self.content)
        card.grid(row=0, column=0, padx=4, pady=8, sticky="ew")
        self.message_label = ctk.CTkLabel(card.content, text=message, justify="left", wraplength=880)
        self.message_label.pack(padx=18, pady=22, anchor="w")

    def show_result(self, result: GenerationResult) -> None:
        self._result = result
        self.shot_cards = []
        self._clear_content()
        row = 0
        status_value = getattr(result.status, "value", str(result.status))
        artifact = result.artifact if isinstance(result.artifact, StoryboardDraft) else None
        metadata = result.metadata
        repair_count = getattr(metadata, "repair_count", 0) or 0

        summary = SoftCard(self.content)
        summary.grid(row=row, column=0, padx=4, pady=(4, 10), sticky="ew")
        summary.content.grid_columnconfigure(0, weight=1)
        self._section_title(summary.content, "生成摘要").grid(row=0, column=0, padx=18, pady=(15, 4), sticky="w")
        summary_lines = [
            f"生成状态：{status_value}",
            f"Storyboard ID：{artifact.storyboard_id if artifact else '未提供'}",
            f"镜头数量：{len(artifact.shots) if artifact else 0}",
            f"目标时长：{artifact.target_duration_s if artifact else '未提供'}",
            f"AI 修正：{'已执行一次' if repair_count == 1 else '未触发'}",
        ]
        parent_request_id = getattr(metadata, "parent_request_id", None)
        if parent_request_id:
            summary_lines.append(f"Parent request ID：{parent_request_id}")
        rendered_lines = list(summary_lines)
        self.summary_label = ctk.CTkLabel(summary.content, text="\n".join(summary_lines), justify="left", wraplength=840)
        self.summary_label.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")
        buttons = ctk.CTkFrame(summary.content, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=18, pady=(0, 15), sticky="w")
        PrimaryButton(buttons, text="复制全部文本", width=118, command=lambda: self._copy(self.rendered_text)).pack(side="left")
        SecondaryButton(buttons, text="复制完整 JSON", width=118, command=self._copy_json, state="normal" if artifact else "disabled").pack(side="left", padx=6)
        SecondaryButton(buttons, text="保存生成结果 JSON", width=144, command=self._save_json, state="normal" if artifact else "disabled").pack(side="left", padx=6)
        StatusText(buttons, textvariable=self.copy_status).pack(side="left", padx=8)
        row += 1

        if artifact is None:
            self.rendered_text = "\n".join(rendered_lines + ["未提供可展示的 Storyboard artifact。"])
            self._section_message(row, "未提供可展示的 Storyboard artifact。")
            return

        shots_section = ctk.CTkFrame(self.content, fg_color="transparent")
        shots_section.grid(row=row, column=0, padx=4, pady=8, sticky="ew")
        shots_section.grid_columnconfigure(0, weight=1)
        self._section_title(shots_section, "镜头列表").grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")
        if not artifact.shots:
            rendered_lines.append("未生成镜头。")
            ctk.CTkLabel(shots_section, text="未生成镜头。", justify="left").grid(row=1, column=0, padx=12, pady=(0, 12), sticky="w")
        for index, shot in enumerate(artifact.shots, start=1):
            # SoftCard's placed shadow/surface is intentionally not used here:
            # a shot body can grow substantially with prompt text.
            card = ctk.CTkFrame(
                shots_section,
                fg_color=CARD_BACKGROUND,
                border_width=1,
                border_color=CARD_BORDER,
                corner_radius=RADIUS_CARD,
            )
            card.grid(row=index, column=0, padx=12, pady=6, sticky="ew")
            card.grid_columnconfigure(0, weight=1)
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.grid(row=0, column=0, padx=16, pady=(14, 5), sticky="ew")
            header.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(header, text=f"Sequence {shot.sequence}  ·  Shot ID {shot.shot_id}  ·  Scene ID {shot.scene_id}", font=ctk.CTkFont(size=15, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(header, text=f"时间：{shot.start_time_s}–{shot.end_time_s} 秒  ·  时长：{shot.duration_s} 秒", text_color=TEXT_SECONDARY, anchor="w").grid(row=1, column=0, pady=(3, 0), sticky="w")
            body = ctk.CTkFrame(card, fg_color="transparent")
            body.grid(row=1, column=0, padx=16, pady=(4, 10), sticky="ew")
            body.grid_columnconfigure(0, weight=1)
            fields = [
                f"Camera：{shot.camera}",
                f"Action：{shot.action}",
                f"Performance：{shot.performance}",
                f"First frame prompt：{shot.first_frame_prompt}",
                f"Video prompt：{shot.video_prompt}",
                f"Sound：{', '.join(shot.sound) if shot.sound else '无'}",
                f"Negative constraints：{', '.join(shot.negative_constraints) if shot.negative_constraints else '无'}",
            ]
            rendered_lines.extend([
                f"Sequence：{shot.sequence}｜Shot ID：{shot.shot_id}｜Scene ID：{shot.scene_id}",
                f"时间：{shot.start_time_s}–{shot.end_time_s} 秒｜时长：{shot.duration_s} 秒",
                *fields,
            ])
            for field_row, field in enumerate(fields):
                ctk.CTkLabel(body, text=field, justify="left", wraplength=800, anchor="w").grid(row=field_row, column=0, pady=2, sticky="ew")
            copy_buttons = ctk.CTkFrame(card, fg_color="transparent")
            copy_buttons.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")
            shot_text = "\n".join(fields)
            PrimaryButton(copy_buttons, text="复制镜头", width=92, command=lambda text=shot_text: self._copy(text)).pack(side="left")
            SecondaryButton(copy_buttons, text="复制 First frame", width=118, command=lambda text=shot.first_frame_prompt: self._copy(text)).pack(side="left", padx=5)
            SecondaryButton(copy_buttons, text="复制 Video prompt", width=122, command=lambda text=shot.video_prompt: self._copy(text)).pack(side="left", padx=5)
            card.header, card.body, card.actions = header, body, copy_buttons
            self.shot_cards.append(card)
        row += 1

        issues_section = SoftCard(self.content)
        issues_section.grid(row=row, column=0, padx=4, pady=8, sticky="ew")
        issues_section.content.grid_columnconfigure(0, weight=1)
        self._section_title(issues_section.content, "验证问题").grid(row=0, column=0, padx=18, pady=(15, 4), sticky="w")
        if not result.issues:
            rendered_lines.append("未发现制片硬规则问题。")
            ctk.CTkLabel(issues_section.content, text="未发现制片硬规则问题。", text_color=SUCCESS, justify="left").grid(
                row=1, column=0, padx=18, pady=(0, 15), sticky="w"
            )
        for index, issue in enumerate(result.issues, start=1):
            code = getattr(issue.code, "value", str(issue.code))
            severity = getattr(issue.severity, "value", str(issue.severity))
            text = (
                f"{severity.upper()}｜{code}\n路径：{issue.path or '未提供'}\n{issue.message}\n"
                f"建议：{issue.suggestion or '未提供'}\n相关 ID：{', '.join(issue.related_ids) if issue.related_ids else '无'}"
            )
            rendered_lines.append(text)
            ctk.CTkLabel(issues_section.content, text=text, justify="left", wraplength=800, anchor="w").grid(
                row=index, column=0, padx=18, pady=6, sticky="ew"
            )
        self.rendered_text = "\n".join(rendered_lines)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def _copy_json(self) -> None:
        if self._result is None or self._result.artifact is None:
            self.copy_status.set("没有可复制的 JSON")
            return
        self._copy(json.dumps(self._result.model_dump(mode="json"), ensure_ascii=False, indent=2))

    def _save_json(self) -> None:
        if self._result is None or self._result.artifact is None:
            self.copy_status.set("没有可保存的 JSON")
            return
        storyboard_id = getattr(self._result.artifact, "storyboard_id", "result")
        path = filedialog.asksaveasfilename(initialfile=f"storyboard-{storyboard_id}.json", defaultextension=".json", filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(self._result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            self.copy_status.set("JSON 保存失败")
            return
        self.copy_status.set("JSON 已保存")

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.copy_status.set("已复制")
        self.after(1500, lambda: self.copy_status.set(""))

    def _section_message(self, row: int, text: str) -> None:
        ctk.CTkLabel(self.content, text=text, justify="left", wraplength=880).grid(
            row=row, column=0, padx=14, pady=12, sticky="w"
        )

    @staticmethod
    def _section_title(parent, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=16, weight="bold"))
