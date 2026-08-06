"""Input view for AI Creator storyboard generation."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from creator_desktop.ui_components import SoftCard, PageTitle, PrimaryButton, RecentProjectRow, SettingsSummary, StatusText
from creator_desktop.ui_theme import (
    CARD_BORDER, CARD_INPUT, ERROR,
    RADIUS_INPUT, SPACE_LARGE, TEXT_MUTED, TEXT_SECONDARY,
)


class CreatorGenerationView(ctk.CTkFrame):
    """Collect Creator inputs and present safe, controller-owned run status."""

    def __init__(
        self,
        master,
        on_generate: Callable[[str, str | None, str | None], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._on_generate = on_generate
        self.api_status = ctk.StringVar(value="API：未配置")
        self.run_status = ctk.StringVar(value="准备就绪")
        self.error_text = ctk.StringVar(value="")
        self.optional_open = False
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        content = ctk.CTkFrame(self, fg_color="transparent", width=820)
        content.grid(row=0, column=0, padx=SPACE_LARGE, pady=(12, 18), sticky="n")
        content.grid_columnconfigure(0, weight=1)

        PageTitle(content, text="新建一部作品").grid(row=0, column=0, pady=(10, 3))
        ctk.CTkLabel(content, text="把一个想法变成完整、可执行、可核验的分镜制作方案。", text_color=TEXT_SECONDARY).grid(row=1, column=0, pady=(0, 14))

        self.creation_card = SoftCard(content, width=820, height=290)
        self.creation_card.grid(row=2, column=0, sticky="ew")
        card = self.creation_card.content
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        self.idea_hint = ctk.CTkLabel(card, text="描述你的故事、题材或创作需求……", text_color=TEXT_MUTED, anchor="w")
        self.idea_hint.grid(row=0, column=0, padx=22, pady=(18, 2), sticky="ew")
        self.idea_textbox = ctk.CTkTextbox(card, wrap="word", height=170, fg_color=CARD_INPUT, border_width=0, corner_radius=20)
        self.idea_textbox.grid(row=1, column=0, padx=14, sticky="nsew")
        self.idea_textbox.bind("<KeyRelease>", self._update_character_count)
        self.card_divider = ctk.CTkFrame(card, height=1, fg_color=CARD_BORDER)
        self.card_divider.grid(row=2, column=0, padx=20, pady=(10, 0), sticky="ew")
        self.footer = ctk.CTkFrame(card, fg_color="transparent")
        self.footer.grid(row=3, column=0, padx=20, pady=12, sticky="ew")
        self.more_button = ctk.CTkButton(self.footer, text="更多创作要求  ›", command=self.toggle_optional_requirements, fg_color="transparent", hover_color="#EEF0F7", text_color=TEXT_SECONDARY, anchor="w", width=138, height=32)
        self.more_button.pack(side="left")
        self.character_count = ctk.StringVar(value="0 字")
        self.character_count_label = StatusText(self.footer, textvariable=self.character_count)
        self.generate_button = PrimaryButton(self.footer, text="开始生成", width=142, command=self._request_generation)
        self.generate_button.pack(side="right")
        self.character_count_label.pack(side="right", padx=(0, 16))

        self.optional = ctk.CTkFrame(content, fg_color="transparent")
        self.optional.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(self.optional, text="视觉风格 style（可选）", text_color=TEXT_SECONDARY).grid(row=0, column=0, padx=(0, 6), pady=(0, 3), sticky="w")
        ctk.CTkLabel(self.optional, text="创作目标 goal（可选）", text_color=TEXT_SECONDARY).grid(row=0, column=1, padx=(6, 0), pady=(0, 3), sticky="w")
        self.style_entry = ctk.CTkEntry(self.optional, placeholder_text="例如：中国工业硬科幻电影", corner_radius=RADIUS_INPUT)
        self.style_entry.grid(row=1, column=0, padx=(0, 6), sticky="ew")
        self.goal_entry = ctk.CTkEntry(self.optional, placeholder_text="例如：生成 60 秒 AI 视频分镜", corner_radius=RADIUS_INPUT)
        self.goal_entry.grid(row=1, column=1, padx=(6, 0), sticky="ew")

        SettingsSummary(content).grid(row=4, column=0, pady=(14, 0), sticky="ew")
        self.error_label = ctk.CTkLabel(content, textvariable=self.error_text, text_color=ERROR, justify="left")
        self.error_label.grid(row=5, column=0, pady=(5, 0), sticky="w")
        self.recent_host = ctk.CTkFrame(content, fg_color="transparent")
        self.recent_host.grid(row=6, column=0, pady=(28, 0), sticky="ew")
        self.recent_empty = ctk.CTkLabel(self.recent_host, text="暂无最近项目", text_color=TEXT_MUTED)
        self.recent_empty.pack(anchor="w")

    def _update_character_count(self, _event=None) -> None:
        self.character_count.set(f"{len(self.idea_textbox.get('1.0', 'end').strip())} 字")

    def toggle_optional_requirements(self) -> None:
        self.optional_open = not self.optional_open
        if self.optional_open:
            self.optional.grid(row=3, column=0, pady=(10, 0), sticky="ew")
            self.more_button.configure(text="收起创作要求  ‹")
        else:
            self.optional.grid_remove()
            self.more_button.configure(text="更多创作要求  ›")

    def set_recent_project(self, title: str | None, detail: str = "", command=None) -> None:
        """Show at most one history entry without changing history persistence."""
        for child in self.recent_host.winfo_children():
            child.destroy()
        if not title:
            self.recent_empty = ctk.CTkLabel(self.recent_host, text="暂无最近项目", text_color=TEXT_MUTED)
            self.recent_empty.pack(anchor="w")
            return
        ctk.CTkLabel(self.recent_host, text="继续最近项目", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 6))
        RecentProjectRow(self.recent_host, title=title, detail=detail, command=command, height=72).pack(fill="x")

    def get_inputs(self) -> tuple[str, str | None, str | None]:
        idea = self.idea_textbox.get("1.0", "end").strip()
        style = self.style_entry.get().strip() or None
        goal = self.goal_entry.get().strip() or None
        return idea, style, goal

    def set_api_configured(self, configured: bool) -> None:
        self.api_status.set("API：已配置" if configured else "API：未配置")

    def set_busy(self, busy: bool, message: str | None = None) -> None:
        state = "disabled" if busy else "normal"
        self.idea_textbox.configure(state=state)
        self.style_entry.configure(state=state)
        self.goal_entry.configure(state=state)
        self.generate_button.configure(state=state)
        if message is not None:
            self.run_status.set(message)
        elif busy:
            self.run_status.set("正在生成 Storyboard，必要时将执行一次 AI 修正。")
        else:
            self.run_status.set("准备就绪")

    def show_error(self, message: str) -> None:
        self.error_text.set(message)
        self.run_status.set("生成失败")

    def clear_error(self) -> None:
        self.error_text.set("")

    def _request_generation(self) -> None:
        self.clear_error()
        idea, style, goal = self.get_inputs()
        if not idea:
            self.show_error("请输入创意 idea 后再生成。")
            return
        try:
            self._on_generate(idea, style, goal)
        except Exception:
            # The controller owns error classification; never expose callback details here.
            self.show_error("无法启动生成，请稍后重试。")
