from __future__ import annotations

import json
import logging
import queue
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from creator_desktop.api_key_dialog import ApiKeyDialog
from creator_desktop.api_key_state import main_api_status, semantic_mode_requires_configuration
from creator_desktop.app_paths import log_dir
from creator_desktop.credentials import CredentialError, has_saved_api_key, load_api_key
from creator_desktop.ui_errors import friendly_error
from creator_desktop.verification_controller import VerificationController
from models import VerificationReport
from verification_service import ReportWriteError, write_report


def _logger() -> logging.Logger:
    logger = logging.getLogger("creator_desktop")
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_dir() / "desktop.log", maxBytes=512_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI视频制作核验器")
        self.geometry("1000x720")
        self.minsize(900, 620)
        self._log = _logger()
        self._controller = VerificationController()
        self._report: VerificationReport | None = None
        self.facts_path = ctk.StringVar()
        self.output_path = ctk.StringVar()
        self.semantic_mode = ctk.StringVar(value="local")
        self.status = ctk.StringVar(value="请选择facts.json和director_output.json。")
        self.summary = ctk.StringVar(value="尚未执行核验")
        self.api_status = ctk.StringVar(value="API：未配置")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        self._refresh_api_status()
        self.after(100, self._poll_events)
        self.after(150, self._offer_first_run_settings)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(self, text="AI视频制作核验器", font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=24, pady=(18, 8), sticky="w"
        )
        files = ctk.CTkFrame(self)
        files.grid(row=1, column=0, padx=24, pady=8, sticky="ew")
        files.grid_columnconfigure(1, weight=1)
        self._path_row(files, 0, "facts.json", self.facts_path, self._choose_facts)
        self._path_row(files, 1, "director_output.json", self.output_path, self._choose_output)

        controls = ctk.CTkFrame(self)
        controls.grid(row=2, column=0, padx=24, pady=8, sticky="ew")
        ctk.CTkRadioButton(controls, text="仅本地硬规则", variable=self.semantic_mode, value="local").pack(
            side="left", padx=12, pady=12
        )
        ctk.CTkRadioButton(controls, text="硬规则 + DeepSeek语义审计", variable=self.semantic_mode, value="semantic").pack(
            side="left", padx=8
        )
        self.start_button = ctk.CTkButton(controls, text="开始核验", command=self._start)
        self.start_button.pack(side="right", padx=12)
        ctk.CTkButton(controls, text="API设置", command=self._open_api_settings).pack(side="right", padx=6)
        ctk.CTkLabel(controls, textvariable=self.api_status).pack(side="right", padx=(4, 10))
        ctk.CTkButton(controls, text="加载错误示例", command=lambda: self._load_example("unknown_character_error")).pack(side="right", padx=6)
        ctk.CTkButton(controls, text="加载正常示例", command=lambda: self._load_example("clean")).pack(side="right", padx=6)

        info = ctk.CTkFrame(self)
        info.grid(row=3, column=0, padx=24, pady=8, sticky="ew")
        ctk.CTkLabel(info, textvariable=self.status).pack(side="left", padx=12, pady=10)
        ctk.CTkLabel(info, textvariable=self.summary, font=ctk.CTkFont(weight="bold")).pack(side="right", padx=12)

        results = ctk.CTkScrollableFrame(self, label_text="问题列表")
        results.grid(row=4, column=0, padx=24, pady=8, sticky="nsew")
        self.results = results
        self.export_button = ctk.CTkButton(self, text="导出JSON报告", command=self._export, state="disabled")
        self.export_button.grid(row=5, column=0, padx=24, pady=(4, 18), sticky="e")

    def _path_row(self, parent, row: int, label: str, variable, command) -> None:
        ctk.CTkLabel(parent, text=label, width=150, anchor="w").grid(row=row, column=0, padx=12, pady=8)
        ctk.CTkEntry(parent, textvariable=variable).grid(row=row, column=1, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(parent, text="选择文件", width=90, command=command).grid(row=row, column=2, padx=4, pady=8)
        ctk.CTkButton(parent, text="清除", width=60, command=lambda: variable.set("")).grid(row=row, column=3, padx=(0, 12), pady=8)

    def _choose_facts(self) -> None:
        path = filedialog.askopenfilename(title="选择facts.json", filetypes=[("JSON 文件", "*.json")])
        if path:
            self.facts_path.set(path)

    def _choose_output(self) -> None:
        path = filedialog.askopenfilename(title="选择director_output.json", filetypes=[("JSON 文件", "*.json")])
        if path:
            self.output_path.set(path)

    def _load_example(self, name: str) -> None:
        root = Path(__file__).resolve().parent.parent / "examples" / name
        self.facts_path.set(str(root / "facts.json"))
        self.output_path.set(str(root / "director_output.json"))
        self.status.set(f"已加载{name}示例。")

    def _open_api_settings(self) -> None:
        ApiKeyDialog(self, on_changed=self._refresh_api_status)

    def _refresh_api_status(self) -> None:
        try:
            configured = has_saved_api_key()
        except CredentialError:
            configured = False
        self.api_status.set(main_api_status(configured))

    def _offer_first_run_settings(self) -> None:
        try:
            missing = not has_saved_api_key()
        except CredentialError:
            missing = False
        if missing:
            self._open_api_settings()

    def _start(self) -> None:
        facts, output = self.facts_path.get().strip(), self.output_path.get().strip()
        if not facts:
            messagebox.showwarning("缺少文件", "请选择facts.json。", parent=self)
            return
        if not output:
            messagebox.showwarning("缺少文件", "请选择director_output.json。", parent=self)
            return
        semantic = self.semantic_mode.get() == "semantic"
        api_key = None
        if semantic:
            try:
                api_key = load_api_key()
            except CredentialError:
                messagebox.showerror("API Key", "无法读取已保存的API Key。", parent=self)
                return
            if semantic_mode_requires_configuration(bool(api_key)):
                self._handle_missing_api_key()
                return
        if not self._controller.start(facts, output, semantic=semantic, api_key=api_key):
            return
        self.start_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.status.set("正在读取文件")
        self._clear_results()

    def _handle_missing_api_key(self) -> None:
        choice = messagebox.askyesnocancel(
            "尚未配置DeepSeek API Key",
            "尚未配置DeepSeek API Key。\n请先打开“API设置”完成配置，或切换到“仅本地硬规则”。",
            parent=self,
        )
        if choice is True:
            self._open_api_settings()
        elif choice is False:
            self.semantic_mode.set("local")
            self.status.set("已切换到仅本地硬规则模式。")

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self._controller.events.get_nowait()
                if kind == "status":
                    self.status.set(str(payload))
                elif kind == "complete":
                    self._on_complete(payload)
                elif kind == "error":
                    self._on_error(payload)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._poll_events)

    def _on_complete(self, report: VerificationReport) -> None:
        self._report = report
        self.status.set("核验完成")
        mode = "硬规则 + 语义审计" if self.semantic_mode.get() == "semantic" else "仅本地硬规则"
        self.summary.set(
            f"{'通过' if report.passed else '未通过'}｜分数 {report.score}｜错误 {report.errors}｜警告 {report.warnings}｜{mode}"
        )
        self._show_issues(report)
        self.start_button.configure(state="normal")
        self.export_button.configure(state="normal")

    def _on_error(self, error: Exception) -> None:
        self._log.warning("verification failed: %s", type(error).__name__)
        self.status.set("核验失败")
        self.start_button.configure(state="normal")
        messagebox.showerror("核验失败", friendly_error(error), parent=self)

    def _clear_results(self) -> None:
        for widget in self.results.winfo_children():
            widget.destroy()

    def _show_issues(self, report: VerificationReport) -> None:
        self._clear_results()
        if not report.issues:
            ctk.CTkLabel(self.results, text="未发现问题。", font=ctk.CTkFont(size=16)).pack(pady=30)
            return
        for issue in report.issues:
            color = "#a33a3a" if issue.severity == "error" else "#8a6d1f"
            card = ctk.CTkFrame(self.results, border_width=1, border_color=color)
            card.pack(fill="x", padx=6, pady=6)
            ctk.CTkLabel(card, text=f"{issue.severity.upper()}  {issue.rule_id}｜{issue.title}", anchor="w").pack(
                fill="x", padx=12, pady=(8, 2)
            )
            for name, value in (("说明", issue.message), ("路径", issue.path), ("证据", issue.evidence), ("建议", issue.suggestion)):
                if value:
                    ctk.CTkLabel(card, text=f"{name}：{value}", anchor="w", justify="left", wraplength=850).pack(
                        fill="x", padx=12, pady=2
                    )

    def _export(self) -> None:
        if not self._report:
            return
        path = filedialog.asksaveasfilename(
            title="导出JSON报告", defaultextension=".json", filetypes=[("JSON 文件", "*.json")]
        )
        if not path:
            return
        try:
            write_report(self._report, path)
        except ReportWriteError as exc:
            messagebox.showerror("导出失败", friendly_error(exc), parent=self)
            return
        self.status.set("报告已导出")

    def _close(self) -> None:
        # Workers are daemon threads and never touch Tk directly.
        self.destroy()
