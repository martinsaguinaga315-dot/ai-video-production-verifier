from __future__ import annotations

from tkinter import filedialog, messagebox

import customtkinter as ctk

from creator_import.extraction_errors import CreatorImportError
from creator_import.file_reader import read_text_file


class NaturalLanguageView(ctk.CTkFrame):
    def __init__(self, master, on_analyze) -> None:
        super().__init__(master)
        self._on_analyze = on_analyze
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self, text="普通创作者模式", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=(16, 2), sticky="w")
        ctk.CTkLabel(self, text="自然语言结构化和语义审计会将相关文本发送到用户自行配置的DeepSeek接口。软件不内置API Key，不提供遥测上传。", wraplength=900, justify="left").grid(row=0, column=0, columnspan=2, padx=20, pady=(45, 8), sticky="w")
        self.script = self._input_panel(0, "剧本或项目要求", "粘贴剧本、人物设定、时长要求、固定台词、禁止项等内容。")
        self.director = self._input_panel(1, "导演方案或分镜方案", "粘贴分镜方案、导演输出、镜头设计、动作路径或视频提示词。")
        self.status = ctk.StringVar(value="请粘贴或导入两份文本。")
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2, padx=20, pady=12, sticky="ew")
        self.analyze_button = ctk.CTkButton(footer, text="自动分析", command=self._on_analyze)
        self.analyze_button.pack(side="left")
        ctk.CTkLabel(footer, textvariable=self.status).pack(side="left", padx=14)

    def _input_panel(self, column: int, title: str, hint: str):
        panel = ctk.CTkFrame(self)
        panel.grid(row=1, column=column, padx=(20, 10) if column == 0 else (10, 20), pady=8, sticky="nsew")
        ctk.CTkLabel(panel, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(padx=12, pady=(12, 2), anchor="w")
        ctk.CTkLabel(panel, text=hint, wraplength=410, justify="left").pack(padx=12, pady=(0, 8), anchor="w")
        box = ctk.CTkTextbox(panel)
        box.pack(fill="both", expand=True, padx=12, pady=6)
        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(buttons, text="导入文件", width=82, command=lambda: self._import(box)).pack(side="left")
        ctk.CTkButton(buttons, text="清空", width=60, command=lambda: box.delete("1.0", "end")).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="加载示例", width=82, command=lambda: self._example(box, title)).pack(side="right")
        return box

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
