"""Input view for AI Creator storyboard generation."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class CreatorGenerationView(ctk.CTkFrame):
    """Collect Creator inputs and present safe, controller-owned run status."""

    def __init__(
        self,
        master,
        on_generate: Callable[[str, str | None, str | None], None],
    ) -> None:
        super().__init__(master)
        self._on_generate = on_generate
        self.api_status = ctk.StringVar(value="API：未配置")
        self.run_status = ctk.StringVar(value="准备就绪")
        self.error_text = ctk.StringVar(value="")
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text="AI 创作生成", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(16, 4), sticky="w"
        )
        ctk.CTkLabel(
            self,
            text="根据创意生成 60 秒 AI 视频分镜。生成过程必要时最多执行一次 AI 修正。",
            justify="left",
        ).grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        inputs = ctk.CTkFrame(self)
        inputs.grid(row=2, column=0, padx=20, pady=8, sticky="nsew")
        inputs.grid_columnconfigure(0, weight=1)
        inputs.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(inputs, text="创意 idea（必填）", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=14, pady=(14, 2), sticky="w"
        )
        ctk.CTkLabel(inputs, text="可输入较长的中文创意、人物、场景和叙事要求。", justify="left").grid(
            row=1, column=0, padx=14, pady=(0, 4), sticky="w"
        )
        self.idea_textbox = ctk.CTkTextbox(inputs, wrap="word")
        self.idea_textbox.grid(row=2, column=0, padx=14, pady=(0, 10), sticky="nsew")

        optional = ctk.CTkFrame(inputs, fg_color="transparent")
        optional.grid(row=3, column=0, padx=14, pady=(0, 14), sticky="ew")
        optional.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(optional, text="视觉风格 style（可选）").grid(row=0, column=0, padx=(0, 6), pady=(0, 3), sticky="w")
        ctk.CTkLabel(optional, text="制作目标 goal（可选）").grid(row=0, column=1, padx=(6, 0), pady=(0, 3), sticky="w")
        self.style_entry = ctk.CTkEntry(optional, placeholder_text="中国工业硬科幻电影")
        self.style_entry.grid(row=1, column=0, padx=(0, 6), sticky="ew")
        self.goal_entry = ctk.CTkEntry(optional, placeholder_text="生成60秒AI视频分镜")
        self.goal_entry.grid(row=1, column=1, padx=(6, 0), sticky="ew")

        status = ctk.CTkFrame(self)
        status.grid(row=3, column=0, padx=20, pady=8, sticky="ew")
        ctk.CTkLabel(status, textvariable=self.api_status).pack(side="left", padx=14, pady=10)
        ctk.CTkLabel(status, textvariable=self.run_status, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=14, pady=10)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, padx=20, pady=(2, 16), sticky="ew")
        self.generate_button = ctk.CTkButton(footer, text="生成 Storyboard", command=self._request_generation)
        self.generate_button.pack(side="left")
        self.error_label = ctk.CTkLabel(footer, textvariable=self.error_text, text_color="#c45050", justify="left")
        self.error_label.pack(side="left", padx=14)

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
