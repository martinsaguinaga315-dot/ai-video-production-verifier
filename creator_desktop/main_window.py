from __future__ import annotations

import json
import logging
import queue
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from creator_desktop.analysis_controller import AnalysisController
from creator_desktop.api_key_dialog import ApiKeyDialog
from creator_desktop.api_key_state import main_api_status, semantic_mode_requires_configuration
from creator_desktop.app_paths import log_dir
from creator_desktop.app_paths import is_smoke_test, resource_path
from app_version import APP_NAME
from creator_desktop.creator_result import CreatorResultFrame
from creator_desktop.creator_generation_controller import CreatorGenerationController
from creator_desktop.creator_generation_result import CreatorGenerationResultFrame
from creator_desktop.creator_generation_view import CreatorGenerationView
from creator_desktop.creator_history_store import CreatorHistoryStore
from creator_desktop.creator_history_view import CreatorHistoryView
from creator_desktop.credentials import CredentialError, has_saved_api_key, load_api_key
from creator_desktop.director_review import DirectorReviewFrame
from creator_desktop.facts_review import FactsReviewFrame, show_json_dialog
from creator_desktop.natural_language_view import NaturalLanguageView
from creator_desktop.mode_switcher import MODE_AI, MODE_CREATOR, MODE_PROFESSIONAL, ModeSwitcher
from creator_desktop.ui_components import PageTitle, PrimaryButton, SecondaryButton, SoftCard, StatusText
from creator_desktop.ui_background import AmbientBackground
from creator_desktop.ui_theme import APP_BACKGROUND, MAIN_CONTENT_WIDE, PAGE_GUTTER, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY, WINDOW_HEIGHT, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_WIDTH
from creator_desktop.ui_errors import friendly_error
from creator_desktop.verification_controller import VerificationController
from creator_import.extraction_errors import CreatorImportError, LLMRequestError
from creator_import.llm_client import DeepSeekClient
from models import DirectorOutput, ProjectFacts, VerificationReport
from story_generation.models import GenerationResult, StoryboardDraft
from verification_service import ReportWriteError, write_report


def _logger() -> logging.Logger:
    logger = logging.getLogger("creator_desktop")
    if not logger.handlers:
        handler = RotatingFileHandler(log_dir() / "desktop.log", maxBytes=512_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def _recent_project_title(record: dict, maximum: int = 16) -> str:
    """Make a compact, safe project label without changing history data."""
    source = str(record.get("name") or record.get("title") or record.get("idea") or "未命名创作")
    source = " ".join(source.split())
    return source if len(source) <= maximum else source[:maximum] + "…"


def _recent_project_detail(record: dict) -> str:
    created_at = str(record.get("created_at") or "")
    try:
        time_text = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone().strftime("今天 %H:%M")
    except ValueError:
        time_text = "最近保存"
    return f"15 秒 · {time_text}   ›"


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.configure(fg_color=APP_BACKGROUND)
        self._log, self._controller, self._analysis = _logger(), VerificationController(), AnalysisController()
        self._creator_generation_events: queue.Queue[dict[str, object]] = queue.Queue()
        self.creator_generation_controller = CreatorGenerationController(self._creator_generation_events)
        self._creator_history_store = CreatorHistoryStore()
        self._last_creator_result = None
        self._active_creator_request = None
        self._report: VerificationReport | None = None
        self._creator_facts: ProjectFacts | None = None
        self._creator_output: DirectorOutput | None = None
        self.facts_path, self.output_path = ctk.StringVar(), ctk.StringVar()
        self.semantic_mode, self.status, self.summary = ctk.StringVar(value="local"), ctk.StringVar(value="请选择facts.json和director_output.json。"), ctk.StringVar(value="尚未执行核验")
        self.api_status = ctk.StringVar(value="API：未配置")
        self.creator_api_status = ctk.StringVar(value="API：未配置")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        self._refresh_api_status()
        self.after(100, self._poll_events)
        if not is_smoke_test():
            self.after(150, self._offer_first_run_settings)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.ambient_background = AmbientBackground(self)
        self.ambient_background.place(x=0, y=0, relwidth=1, relheight=1)
        self.ambient_background.tk.call("lower", self.ambient_background._w)
        header = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        self.mode_switcher = ModeSwitcher(header, self._switch_mode)
        self.mode_switcher.grid(row=0, column=0, padx=24, pady=16, sticky="w")
        tools = ctk.CTkFrame(header, fg_color="transparent")
        tools.grid(row=0, column=2, padx=24, pady=16, sticky="e")
        SecondaryButton(tools, text="历史", width=76, command=self._open_creator_history_from_header).pack(side="left", padx=4)
        StatusText(tools, textvariable=self.creator_api_status).pack(side="left", padx=12)
        SecondaryButton(tools, text="设置", width=76, command=self._open_api_settings).pack(side="left", padx=4)
        self.mode = ctk.StringVar(value="AI 创作生成")
        self.creator_generation_host = ctk.CTkFrame(self, fg_color="transparent")
        self.creator_host = ctk.CTkFrame(self, fg_color="transparent")
        self.professional_host = ctk.CTkFrame(self, fg_color="transparent")
        self.creator_generation_host.grid(row=1, column=0, sticky="nsew")
        self.creator_host.grid(row=1, column=0, sticky="nsew")
        self.professional_host.grid(row=1, column=0, sticky="nsew")
        self.creator_generation_host.grid_rowconfigure(0, weight=1); self.creator_generation_host.grid_columnconfigure(0, weight=1)
        self.creator_host.grid_rowconfigure(0, weight=1); self.creator_host.grid_columnconfigure(0, weight=1)
        self.professional_host.grid_rowconfigure(4, weight=1); self.professional_host.grid_columnconfigure(0, weight=1)
        self.creator_view = NaturalLanguageView(
            self.creator_host,
            self._start_creator_analysis,
            self._open_api_settings,
            self.creator_api_status,
        )
        self.creator_view.grid(row=0, column=0, sticky="nsew")
        self._build_creator_generation()
        self._build_professional()
        self._switch_mode(MODE_AI)

    def _build_creator_generation(self) -> None:
        host = self.creator_generation_host
        self.creator_generation_view = CreatorGenerationView(host, self._on_creator_generate)
        self._refresh_recent_creator_project()
        self.creator_generation_result_host = ctk.CTkFrame(host, fg_color="transparent")
        self.creator_generation_result_host.grid_rowconfigure(0, weight=1)
        self.creator_generation_result_host.grid_columnconfigure(0, weight=1)
        self.creator_generation_result_frame = CreatorGenerationResultFrame(
            self.creator_generation_result_host,
            on_back=self._show_creator_generation_input,
        )
        self.creator_generation_result_frame.grid(row=0, column=0, sticky="nsew")
        self.creator_history_view = CreatorHistoryView(
            host,
            self._creator_history_store,
            self._show_history_result,
            self._delete_history_record,
            self._show_creator_generation_input,
        )
        self._show_creator_generation_input()

    def _build_professional(self) -> None:
        host = self.professional_host
        self._build_professional_light_layout(host)

    def _build_professional_light_layout(self, host) -> None:
        host.grid_rowconfigure(0, weight=1)
        content = ctk.CTkFrame(host, fg_color="transparent", width=MAIN_CONTENT_WIDE)
        content.grid(row=0, column=0, padx=PAGE_GUTTER, pady=(12, 18), sticky="new")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(5, weight=1)
        PageTitle(content, text="专业 JSON 核验").grid(row=0, column=0, pady=(10, 3))
        ctk.CTkLabel(content, text="导入事实数据和导演输出，执行结构化规则核验。", text_color=TEXT_SECONDARY).grid(row=1, column=0, pady=(0, 14))

        self.professional_files_card = SoftCard(content, height=138)
        self.professional_files_card.grid(row=2, column=0, sticky="ew")
        files = self.professional_files_card.content
        files.grid_columnconfigure(1, weight=1)
        self._light_path_row(files, 0, "facts.json", self.facts_path, self._choose_facts)
        self._light_path_row(files, 1, "director_output.json", self.output_path, self._choose_output)

        self.professional_controls_card = SoftCard(content, height=82)
        self.professional_controls_card.grid(row=3, column=0, pady=(14, 0), sticky="ew")
        controls = self.professional_controls_card.content
        ctk.CTkRadioButton(controls, text="仅本地硬规则", variable=self.semantic_mode, value="local").pack(side="left", padx=(20, 10), pady=18)
        ctk.CTkRadioButton(controls, text="硬规则 + DeepSeek语义审计", variable=self.semantic_mode, value="semantic").pack(side="left", padx=8)
        self.start_button = PrimaryButton(controls, text="开始核验", width=142, command=self._start)
        self.start_button.pack(side="right", padx=20, pady=18)
        SecondaryButton(controls, text="加载错误示例", width=108, command=lambda: self._load_example("unknown_character_error")).pack(side="right", padx=8, pady=18)
        SecondaryButton(controls, text="加载正常示例", width=108, command=lambda: self._load_example("clean")).pack(side="right", pady=18)

        self.professional_status_card = SoftCard(content, height=76)
        self.professional_status_card.grid(row=4, column=0, pady=(14, 0), sticky="ew")
        info = self.professional_status_card.content
        ctk.CTkLabel(info, text="当前说明", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=(13, 0))
        StatusText(info, textvariable=self.status).pack(side="left", padx=20, pady=(2, 12))
        ctk.CTkLabel(info, textvariable=self.summary, text_color=TEXT_PRIMARY, font=ctk.CTkFont(weight="bold")).pack(side="right", padx=20, pady=(2, 12))

        self.professional_results_card = SoftCard(content, height=300)
        self.professional_results_card.grid(row=5, column=0, pady=(14, 0), sticky="nsew")
        results_body = self.professional_results_card.content
        results_body.grid_columnconfigure(0, weight=1)
        results_body.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(results_body, text="问题列表", text_color=TEXT_PRIMARY, font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(16, 8), sticky="w")
        self.export_button = SecondaryButton(results_body, text="导出 JSON 报告", width=126, command=self._export, state="disabled")
        self.export_button.grid(row=0, column=0, padx=20, pady=(12, 6), sticky="e")
        self.results = ctk.CTkScrollableFrame(results_body, fg_color="transparent", label_text="")
        self.results.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")

    def _light_path_row(self, parent, row, label, variable, command) -> None:
        ctk.CTkLabel(parent, text=label, text_color=TEXT_PRIMARY, width=170, anchor="w").grid(row=row, column=0, padx=(20, 8), pady=10)
        ctk.CTkEntry(parent, textvariable=variable, fg_color="#FAFBFD", border_color="#DCE3EC").grid(row=row, column=1, padx=8, pady=10, sticky="ew")
        SecondaryButton(parent, text="选择文件", width=90, command=command).grid(row=row, column=2, padx=4, pady=10)
        SecondaryButton(parent, text="清除", width=64, command=lambda: variable.set("")).grid(row=row, column=3, padx=(4, 20), pady=10)

    def _switch_mode(self, value: str) -> None:
        if getattr(self, "creator_generation_view", None) is not None and self.creator_generation_view.generate_button.cget("state") == "disabled":
            return
        self.creator_generation_host.grid_remove()
        self.creator_host.grid_remove()
        self.professional_host.grid_remove()
        mapping = {
            MODE_AI: "AI 创作生成", "AI 创作生成": "AI 创作生成",
            MODE_CREATOR: "普通创作者模式", "普通创作者模式": "普通创作者模式",
            MODE_PROFESSIONAL: "专业JSON模式", "专业JSON模式": "专业JSON模式",
        }
        internal_value = mapping.get(value, value)
        if hasattr(self, "mode"):
            self.mode.set(internal_value)
        if value == MODE_AI or internal_value == "AI 创作生成":
            self.creator_generation_host.grid()
            if getattr(self, "creator_generation_view", None) is not None:
                self._show_creator_generation_input()
        elif internal_value == "普通创作者模式":
            self.creator_host.grid()
        else:
            self.professional_host.grid()

    def _choose_facts(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if path: self.facts_path.set(path)

    def _choose_output(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if path: self.output_path.set(path)

    def _load_example(self, name: str) -> None:
        root = resource_path("examples", name)
        self.facts_path.set(str(root / "facts.json")); self.output_path.set(str(root / "director_output.json")); self.status.set(f"已加载{name}示例。")

    def _open_api_settings(self) -> None:
        ApiKeyDialog(self, on_changed=self._refresh_api_status)

    def _refresh_api_status(self) -> None:
        try: configured = has_saved_api_key()
        except CredentialError: configured = False
        status = main_api_status(configured)
        self.api_status.set(status)
        self.creator_api_status.set(status)
        if hasattr(self, "creator_generation_view"):
            self.creator_generation_view.set_api_configured(configured)

    def _offer_first_run_settings(self) -> None:
        try: missing = not has_saved_api_key()
        except CredentialError: missing = False
        if missing: self._open_api_settings()

    def _start(self) -> None:
        facts, output = self.facts_path.get().strip(), self.output_path.get().strip()
        if not facts or not output:
            messagebox.showwarning("缺少文件", "请选择facts.json和director_output.json。", parent=self); return
        semantic, api_key = self.semantic_mode.get() == "semantic", None
        if semantic:
            try: api_key = load_api_key()
            except CredentialError: messagebox.showerror("API Key", "无法读取已保存的API Key。", parent=self); return
            if semantic_mode_requires_configuration(bool(api_key)):
                self._handle_missing_api_key(); return
        if self._controller.start(facts, output, semantic=semantic, api_key=api_key):
            MainWindow._reset_run_state(self)
            self.start_button.configure(state="disabled"); self.status.set("正在读取文件")

    def _handle_missing_api_key(self) -> None:
        choice = messagebox.askyesnocancel("尚未配置DeepSeek API Key", "尚未配置DeepSeek API Key。\n请先打开“API设置”完成配置，或切换到“仅本地硬规则”。", parent=self)
        if choice is True: self._open_api_settings()
        elif choice is False: self.semantic_mode.set("local"); self.status.set("已切换到仅本地硬规则模式。")

    def _start_creator_analysis(self) -> None:
        script, director = self.creator_view.texts()
        if not script or not director:
            messagebox.showwarning("缺少文本", "请同时提供剧本或项目要求，以及导演方案或分镜方案。", parent=self); return
        try: client = DeepSeekClient()
        except LLMRequestError:
            messagebox.showwarning("需要API Key", "自然语言解析需要DeepSeek API Key。\n请先完成API设置，或切换到专业JSON模式使用本地硬规则。", parent=self); return
        self._creator_script, self._creator_director, self._creator_client = script, director, client
        if self._analysis.start_facts(script, client): self.creator_view.set_busy(True, "正在读取剧本")

    def _on_creator_generate(self, idea: str, style: str | None, goal: str | None, target_duration_s: int = 60, aspect_ratio: str = "16:9") -> None:
        self.creator_generation_view.clear_error()
        try:
            api_key = load_api_key()
        except CredentialError:
            api_key = None
        if not api_key:
            self.creator_generation_view.set_api_configured(False)
            self.creator_generation_view.show_error("请先在 API 设置中保存 DeepSeek API Key。")
            self._open_api_settings()
            return
        self.creator_generation_view.set_api_configured(True)
        self.creator_generation_result_frame.clear()
        self._active_creator_request = {"idea": idea, "style": style, "goal": goal}
        self.creator_generation_view.set_busy(True)
        try:
            started = self.creator_generation_controller.start(
                idea=idea,
                style=style,
                goal=goal,
                target_duration_s=target_duration_s,
                aspect_ratio=aspect_ratio,
                api_key=api_key,
            )
        except ValueError as exc:
            self.creator_generation_view.set_busy(False)
            self.creator_generation_view.show_error(str(exc))
            return
        if not started:
            self.creator_generation_view.set_busy(True, "正在生成 Storyboard，必要时将执行一次 AI 修正。")
            self.creator_generation_view.show_error("已有生成任务正在运行。")

    def _show_creator_generation_input(self) -> None:
        self._refresh_recent_creator_project()
        self.creator_generation_view.grid_remove()
        self.creator_generation_result_host.grid_remove()
        self.creator_history_view.grid_remove()
        self.creator_generation_view.grid(row=0, column=0, sticky="nsew")

    def _open_creator_history_from_header(self) -> None:
        if self.creator_generation_view.generate_button.cget("state") == "disabled":
            return
        self.mode_switcher.current_mode = MODE_AI
        self.mode_switcher._update_button()
        self._switch_mode(MODE_AI)
        self._show_creator_history()

    def _refresh_recent_creator_project(self) -> None:
        if not hasattr(self, "creator_generation_view"):
            return
        records = self._creator_history_store.list_records()
        if not records:
            self.creator_generation_view.set_recent_project(None)
            return
        record = records[0]
        title = _recent_project_title(record)
        self.creator_generation_view.set_recent_project(title, _recent_project_detail(record), command=lambda: self._show_history_result(record))

    def _show_creator_generation_result(self) -> None:
        # History results navigate within the AI host; do not call _switch_mode
        # because selecting MODE_AI intentionally returns to the input subview.
        self.creator_generation_host.grid(row=1, column=0, sticky="nsew")
        self.creator_generation_view.grid_remove()
        self.creator_history_view.grid_remove()
        self.creator_generation_result_host.grid(row=0, column=0, sticky="nsew")
        self._log.info("history_result_host_shown")

    def _show_creator_history(self) -> None:
        self.creator_generation_view.grid_remove(); self.creator_generation_result_host.grid_remove()
        self.creator_history_view.refresh(); self.creator_history_view.grid(row=0, column=0, sticky="nsew")

    def _show_last_creator_result(self) -> None:
        if self._last_creator_result is not None:
            self.creator_generation_result_frame.show_result(self._last_creator_result)
            self._show_creator_generation_result()

    def _delete_history_record(self, history_id: str) -> None:
        self._creator_history_store.delete(history_id)

    def _show_history_result(self, record: dict) -> None:
        history_id = record.get("history_id", "unknown")
        self._log.info("history_view_clicked history_id=%s", history_id)
        try:
            self._log.info("history_result_validation_started history_id=%s", history_id)
            raw_result = record["result"]
            result = GenerationResult.model_validate(raw_result)
            self._log.info("generation_result_validation_ok history_id=%s", history_id)
            artifact = result.artifact
            if isinstance(artifact, dict):
                artifact = StoryboardDraft.model_validate(artifact)
                result = result.model_copy(update={"artifact": artifact})
            elif not isinstance(artifact, StoryboardDraft):
                raise TypeError(f"Unsupported history artifact type: {type(artifact).__name__}")
            self._log.info("storyboard_validation_ok history_id=%s", history_id)
        except Exception:
            self._log.exception("Unable to restore creator history result history_id=%s", history_id)
            messagebox.showerror("历史记录读取失败", "无法读取该历史结果，记录可能来自旧版本或数据已损坏。", parent=self)
            return
        self._last_creator_result = result
        if hasattr(self, "creator_generation_last_button"):
            self.creator_generation_last_button.configure(state="normal")
        self._log.info("history_result_render_started history_id=%s", history_id)
        self.creator_generation_result_frame.show_result(result)
        self._show_creator_generation_result()
        self._log.info("history_result_render_completed history_id=%s", history_id)

    def _show_creator(self, widget) -> None:
        for child in self.creator_host.winfo_children(): child.grid_remove()
        widget.grid(row=0, column=0, sticky="nsew")

    def _show_facts_review(self, facts: ProjectFacts) -> None:
        self._creator_facts = facts
        review = FactsReviewFrame(self.creator_host, facts, self._confirm_facts, self._return_to_creator, self._retry_facts, lambda: show_json_dialog(self, facts))
        self._show_creator(review)

    def _confirm_facts(self, facts: ProjectFacts) -> None:
        self._creator_facts = facts
        if self._analysis.start_director(self._creator_director, facts, self._creator_client):
            self.creator_view.set_busy(True, "正在读取导演方案")

    def _retry_facts(self) -> None:
        if self._analysis.start_facts(self._creator_script, self._creator_client): self.creator_view.set_busy(True, "正在提取项目事实")

    def _return_to_creator(self) -> None:
        self.creator_view.set_busy(False); self._show_creator(self.creator_view)

    def _show_director_review(self, output: DirectorOutput) -> None:
        self._creator_output = output
        self._show_creator(DirectorReviewFrame(self.creator_host, output, self._creator_verify, self._return_to_creator, self._retry_director))

    def _retry_director(self) -> None:
        if self._analysis.start_director(self._creator_director, self._creator_facts, self._creator_client): self.creator_view.set_busy(True, "正在解析导演方案")

    def _creator_verify(self, semantic: bool) -> None:
        api_key = None
        if semantic:
            try: api_key = load_api_key()
            except CredentialError: api_key = None
            if not api_key: self._handle_missing_api_key(); return
        if self._analysis.start_verification(self._creator_facts, self._creator_output, semantic=semantic, api_key=api_key): self.creator_view.set_busy(True, "正在执行本地硬规则")

    def _show_creator_result(self, report: VerificationReport) -> None:
        self._show_creator(CreatorResultFrame(self.creator_host, report, lambda: self._export_creator(report, "report"), lambda: self._export_creator(self._creator_facts, "facts"), lambda: self._export_creator(self._creator_output, "output"), self._return_to_creator))

    def _export_creator(self, value, kind: str) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON 文件", "*.json")])
        if not path: return
        try:
            if kind == "report": write_report(value, path)
            else: Path(path).write_text(json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (ReportWriteError, OSError): messagebox.showerror("导出失败", "无法写入文件，请检查保存位置和权限。", parent=self)

    def _poll_events(self) -> None:
        self._poll_professional_events(); self._poll_creator_events(); self._poll_creator_generation_events()
        if self.winfo_exists(): self.after(100, self._poll_events)

    def _poll_professional_events(self) -> None:
        try:
            while True:
                kind, payload = self._controller.events.get_nowait()
                if kind == "status": self.status.set(str(payload))
                elif kind == "complete": self._on_complete(payload)
                else: self._on_error(payload)
        except queue.Empty: pass

    def _poll_creator_events(self) -> None:
        try:
            while True:
                kind, payload = self._analysis.events.get_nowait()
                if kind == "status": self.creator_view.set_busy(True, str(payload))
                elif kind == "facts_ready": self.creator_view.set_busy(False); self._show_facts_review(payload)
                elif kind == "director_ready": self.creator_view.set_busy(False); self._show_director_review(payload)
                elif kind == "verification_complete": self.creator_view.set_busy(False); self._show_creator_result(payload)
                elif kind == "error": self.creator_view.set_busy(False); self._return_to_creator(); messagebox.showerror("自动结构化失败", self._creator_error_text(payload), parent=self)
        except queue.Empty: pass

    def _poll_creator_generation_events(self) -> None:
        try:
            while True:
                event = self._creator_generation_events.get_nowait()
                event_type = event.get("type")
                if event_type == "status":
                    self.creator_generation_view.set_busy(True, str(event.get("message", "")))
                elif event_type == "complete":
                    self.creator_generation_view.set_busy(False, "生成完成")
                    result = event["result"]
                    self._last_creator_result = result
                    if hasattr(self, "creator_generation_last_button"):
                        self.creator_generation_last_button.configure(state="normal")
                    if getattr(self, "_active_creator_request", None) is not None:
                        try:
                            self._creator_history_store.save(**self._active_creator_request, result=result)
                        except Exception:
                            self.creator_generation_view.show_error("历史记录保存失败，但生成结果可正常查看。")
                    if hasattr(self, "creator_history_view"):
                        self.creator_history_view.refresh()
                    self.creator_generation_result_frame.show_result(result)
                    self._show_creator_generation_result()
                elif event_type == "error":
                    self.creator_generation_view.set_busy(False, "生成失败")
                    self.creator_generation_view.show_error(str(event.get("message", "生成失败，请稍后重试。")))
                    self._show_creator_generation_input()
        except queue.Empty: pass

    def _creator_error_text(self, error: Exception) -> str:
        if isinstance(error, CreatorImportError):
            return str(error) + ("\n" + "\n".join(error.details[:5]) if error.details else "")
        return "自动结构化失败，请返回修改原文后重试。"

    def _on_complete(self, report: VerificationReport) -> None:
        self._report = report
        semantic_unavailable = any(issue.rule_id == "SEMANTIC_AUDIT_NOT_EXECUTED" for issue in report.issues)
        self.status.set("本地硬规则已完成；DeepSeek语义审计未执行" if semantic_unavailable else "核验完成")
        self.summary.set(f"{'通过' if report.passed else '未通过'}｜分数 {report.score}｜错误 {report.errors}｜警告 {report.warnings}")
        self._show_issues(report); self.start_button.configure(state="normal"); self.export_button.configure(state="normal")

    def _on_error(self, error: Exception) -> None:
        self._log.warning("verification failed: %s", type(error).__name__)
        MainWindow._reset_run_state(self)
        self.status.set("核验失败")
        self.start_button.configure(state="normal")
        messagebox.showerror("核验失败", friendly_error(error), parent=self)

    def _reset_run_state(self) -> None:
        """Clear all result state so an earlier run can never be mistaken for this one."""
        self._report = None
        self.summary.set("尚未执行核验")
        MainWindow._clear_results(self)
        self.export_button.configure(state="disabled")

    def _clear_results(self) -> None:
        for widget in self.results.winfo_children(): widget.destroy()

    def _show_issues(self, report: VerificationReport) -> None:
        self._clear_results()
        if not report.issues: ctk.CTkLabel(self.results, text="未发现问题。", font=ctk.CTkFont(size=16)).pack(pady=30)
        for issue in report.issues:
            ctk.CTkLabel(self.results, text=f"{issue.severity.upper()} {issue.rule_id}｜{issue.title}\n{issue.message}\n路径：{issue.path}\n建议：{issue.suggestion}", justify="left", wraplength=900, anchor="w").pack(fill="x", padx=8, pady=7)

    def _export(self) -> None:
        if not self._report: return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON 文件", "*.json")])
        if path:
            try: write_report(self._report, path); self.status.set("报告已导出")
            except ReportWriteError as exc: messagebox.showerror("导出失败", friendly_error(exc), parent=self)

    def _close(self) -> None:
        self.destroy()
