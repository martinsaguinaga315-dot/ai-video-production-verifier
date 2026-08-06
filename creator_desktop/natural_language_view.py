from __future__ import annotations

from tkinter import filedialog, messagebox

import customtkinter as ctk

from creator_desktop.ui_components import PageTitle, PrimaryButton, SecondaryButton, SoftCard, StatusText
from creator_desktop.ui_theme import CARD_INPUT, MAIN_CONTENT_WIDE, PAGE_GUTTER, TEXT_PRIMARY, TEXT_SECONDARY
from creator_import.extraction_errors import CreatorImportError
from creator_import.file_reader import read_text_file


class NaturalLanguageView(ctk.CTkFrame):
    def __init__(self, master, on_analyze, on_open_api_settings, api_status) -> None:
        super().__init__(master)
        self._on_analyze = on_analyze
        # API设置 is provided by the shared top toolbar, not this page.
        self.api_status = api_status  # compatibility only; the top bar owns its display
        self._build_light_layout()

    def _build_light_layout(self) -> None:
        self.configure(fg_color="transparent")
        self._layout_job = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.content = ctk.CTkFrame(self, fg_color="transparent", width=MAIN_CONTENT_WIDE)
        self.content.grid(row=0, column=0, padx=PAGE_GUTTER, pady=(12, 18), sticky="new")
        self.content.grid_columnconfigure(0, weight=1)
        PageTitle(self.content, text="普通创作").grid(row=0, column=0, pady=(10, 3))
        ctk.CTkLabel(self.content, text="通过脚本要求和导演方案，快速生成结构化分析结果。", text_color=TEXT_SECONDARY).grid(row=1, column=0, pady=(0, 14))
        self.input_area = ctk.CTkFrame(self.content, fg_color="transparent")
        self.input_area.grid(row=2, column=0, sticky="ew")
        self.input_area.grid_columnconfigure((0, 1), weight=1, uniform="creator_inputs")
        self.script_card, self.script = self._light_input_panel("脚本或项目要求", "请包含镜头编号、总时长、每个镜头起止时间，以及人物、固定台词和禁止项等内容。")
        self.director_card, self.director = self._light_input_panel("导演方案或分镜方案", "粘贴分镜方案、导演输出、镜头设计、动作路径或视频提示词。")
        self._place_input_cards(True)
        self.status = ctk.StringVar(value="请粘贴或导入两份文本。")
        self.footer = ctk.CTkFrame(self.content, fg_color="transparent")
        self.footer.grid(row=3, column=0, pady=(14, 0), sticky="ew")
        StatusText(self.footer, textvariable=self.status).pack(side="left", pady=4)
        self.analyze_button = PrimaryButton(self.footer, text="自动分析", width=142, command=self._on_analyze)
        self.analyze_button.pack(side="right")
        self.bind("<Configure>", self._queue_responsive_layout)

    def _light_input_panel(self, title: str, hint: str):
        panel = SoftCard(self.input_area, height=400)
        body = panel.content
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(body, text=title, text_color=TEXT_PRIMARY, font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(18, 3), sticky="w")
        ctk.CTkLabel(body, text=hint, text_color=TEXT_SECONDARY, wraplength=470, justify="left").grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        box = ctk.CTkTextbox(body, wrap="word", height=250, fg_color=CARD_INPUT, border_width=0, corner_radius=18)
        box.grid(row=2, column=0, padx=14, sticky="nsew")
        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=14, pady=12, sticky="ew")
        SecondaryButton(buttons, text="导入文件", width=90, command=lambda: self._import(box)).pack(side="left")
        SecondaryButton(buttons, text="清空", width=68, command=lambda: box.delete("1.0", "end")).pack(side="left", padx=8)
        SecondaryButton(buttons, text="加载示例", width=90, command=lambda: self._example(box, title)).pack(side="right")
        return panel, box

    def _place_input_cards(self, two_columns: bool) -> None:
        self.script_card.grid_forget(); self.director_card.grid_forget()
        if two_columns:
            self.script_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
            self.director_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
        else:
            self.input_area.grid_columnconfigure(0, weight=1)
            self.script_card.grid(row=0, column=0, pady=(0, 12), sticky="nsew")
            self.director_card.grid(row=1, column=0, sticky="nsew")

    def _queue_responsive_layout(self, _event=None) -> None:
        if self._layout_job is None:
            self._layout_job = self.after_idle(self._apply_responsive_layout)

    def _apply_responsive_layout(self) -> None:
        self._layout_job = None
        self._place_input_cards(self.winfo_width() >= 940)

    def _import(self, box) -> None:
        path = filedialog.askopenfilename(filetypes=[("支持的文本", "*.txt *.md *.docx *.json")])
        if not path:
            return
        try:
            result = read_text_file(path)
        except CreatorImportError as exc:
            messagebox.showwarning("导入失败", str(exc), parent=self)
            return
        box.delete("1.0", "end")
        box.insert("1.0", result.text)
        self.status.set(f"已导入{result.file_type.upper()}文件（{result.char_count}字）。")

    def _example(self, box, title: str) -> None:
        text = "项目《雨夜》共2秒，1个镜头。人物小雨穿蓝外套，持有雨伞。S01从0秒到2秒，小雨撑伞，说：别等我。禁止爆炸。"
        if "导演" in title:
            text = "S01 0-2秒：小雨穿蓝外套撑伞，开场和结尾均为撑伞状态。台词：小雨：别等我。"
        box.delete("1.0", "end")
        box.insert("1.0", text)

    def texts(self) -> tuple[str, str]:
        return self.script.get("1.0", "end").strip(), self.director.get("1.0", "end").strip()

    def set_busy(self, busy: bool, status: str = "") -> None:
        self.analyze_button.configure(state="disabled" if busy else "normal")
        if status:
            self.status.set(status)
