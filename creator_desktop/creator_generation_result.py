"""Read-only result display for AI Creator storyboard generation."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from story_generation.models import GenerationResult, PromptPack, StoryboardDraft
from story_generation.services.prompt_pack_service import PromptPackService
from story_generation.services.ai_prompt_pack_service import AiPromptPackService, AiPromptPackValidationError
from story_generation.platform_adapters import PromptTargetPlatform, adapt_prompt_shot
from story_generation.clients.deepseek_client import DEFAULT_DEEPSEEK_MODEL, DeepSeekApiError, DeepSeekClient
from creator_desktop.creator_prompt_pack_store import CreatorPromptPackStore
from creator_desktop.credentials import CredentialError, has_saved_api_key, load_api_key
from creator_desktop.ui_components import PageTitle, PrimaryButton, SecondaryButton, SoftCard, StatusText
from creator_desktop.ui_theme import CARD_BACKGROUND, CARD_BORDER, MAIN_CONTENT_WIDE, PAGE_GUTTER, RADIUS_CARD, SUCCESS, TEXT_SECONDARY


class CreatorGenerationResultFrame(ctk.CTkFrame):
    """Render a GenerationResult without invoking any generation services."""

    def __init__(self, master, on_back=None, prompt_pack_store: CreatorPromptPackStore | None = None, on_configure_api_key=None, ai_service_factory=None) -> None:
        super().__init__(master, fg_color="transparent")
        self.rendered_text = ""
        self._result: GenerationResult | None = None
        self._prompt_pack: PromptPack | None = None
        self._prompt_service = PromptPackService()
        self._prompt_pack_store = prompt_pack_store or CreatorPromptPackStore()
        self._on_configure_api_key = on_configure_api_key
        self._ai_service_factory = ai_service_factory or (lambda key, model: AiPromptPackService(DeepSeekClient(api_key=key, model=model)))
        self._ai_running = False
        self.deepseek_model = ctk.StringVar(value="V4 Flash")
        self.target_platform = ctk.StringVar(value="通用")
        self.shot_selection: dict[str, ctk.BooleanVar] = {}
        self.prompt_language = ctk.StringVar(value="中文")
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
        self._prompt_pack = None
        self.shot_selection = {}
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
        self._prompt_pack = None
        self.shot_selection = {}
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

        restored_prompt_pack = self._prompt_pack_store.load(artifact.storyboard_id)
        if restored_prompt_pack is not None:
            self._prompt_pack = restored_prompt_pack
            self.prompt_language.set("English" if restored_prompt_pack.output_language == "en" else "中文")

        prompt_controls = SoftCard(self.content)
        prompt_controls.grid(row=row, column=0, padx=4, pady=(0, 8), sticky="ew")
        prompt_controls.content.grid_columnconfigure(0, weight=1)
        self._section_title(prompt_controls.content, "生产提示词").grid(row=0, column=0, padx=18, pady=(15, 4), sticky="w")
        ctk.CTkLabel(prompt_controls.content, text="从当前 Storyboard 本地生成生产级提示词，无需 API Key。", justify="left", wraplength=820).grid(row=1, column=0, padx=18, pady=(0, 8), sticky="w")
        ctk.CTkLabel(prompt_controls.content, text="提示词语言：").grid(row=2, column=0, padx=18, sticky="w")
        ctk.CTkOptionMenu(prompt_controls.content, values=["中文", "English"], variable=self.prompt_language, command=self._on_prompt_language_changed).grid(row=2, column=0, padx=(100, 18), pady=(0, 8), sticky="w")
        ctk.CTkLabel(prompt_controls.content, text="DeepSeek 模型：").grid(row=2, column=0, padx=(250, 18), sticky="w")
        ctk.CTkOptionMenu(prompt_controls.content, values=["V4 Flash", "V4 Pro"], variable=self.deepseek_model).grid(row=2, column=0, padx=(350, 18), pady=(0, 8), sticky="w")
        ctk.CTkLabel(prompt_controls.content, text="目标平台：").grid(row=2, column=0, padx=(510, 18), sticky="w")
        ctk.CTkOptionMenu(prompt_controls.content, values=["通用", "可灵", "即梦", "Runway", "Veo"], variable=self.target_platform).grid(row=2, column=0, padx=(590, 18), pady=(0, 8), sticky="w")
        prompt_actions = ctk.CTkFrame(prompt_controls.content, fg_color="transparent")
        prompt_actions.grid(row=3, column=0, padx=18, pady=(0, 15), sticky="w")
        self.ai_all_button = PrimaryButton(prompt_actions, text="AI 生成全部提示词", width=158, command=self.generate_all_ai_prompt_pack)
        self.ai_all_button.pack(side="left")
        self.ai_selected_button = SecondaryButton(prompt_actions, text="AI 生成选中镜头", width=148, command=self.generate_selected_ai_prompt_pack, state="disabled")
        self.ai_selected_button.pack(side="left", padx=6)
        PrimaryButton(prompt_actions, text="生成全部提示词", width=150, command=self.generate_all_prompt_pack).pack(side="left")
        SecondaryButton(prompt_actions, text="全选", width=92, command=self.select_all_shots).pack(side="left", padx=6)
        SecondaryButton(prompt_actions, text="取消全选", width=112, command=self.clear_shot_selection).pack(side="left", padx=6)
        self.generate_selected_button = SecondaryButton(prompt_actions, text="生成选中镜头", width=140, command=self.generate_selected_prompt_pack, state="disabled")
        self.generate_selected_button.pack(side="left", padx=6)
        try:
            configured = has_saved_api_key()
        except CredentialError:
            configured = False
        self.ai_status_label = ctk.CTkLabel(prompt_controls.content, text=f"DeepSeek：{'已配置' if configured else '未配置'}", text_color=TEXT_SECONDARY)
        self.ai_status_label.grid(row=4, column=0, padx=18, pady=(0, 12), sticky="w")
        if not configured and self._on_configure_api_key:
            SecondaryButton(prompt_controls.content, text="配置 API Key", width=112, command=self._on_configure_api_key).grid(row=4, column=0, padx=(130, 18), pady=(0, 12), sticky="w")
        row += 1

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
            selected = ctk.BooleanVar(value=False)
            self.shot_selection[shot.shot_id] = selected
            ctk.CTkCheckBox(header, text="选择镜头", variable=selected, command=self._update_selected_button).grid(row=0, column=1, sticky="e")
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

        self.prompt_pack_section = ctk.CTkFrame(self.content, fg_color="transparent")
        self.prompt_pack_section.grid(row=row, column=0, padx=4, pady=8, sticky="ew")
        self.prompt_pack_section.grid_columnconfigure(0, weight=1)
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
        self._storyboard_rendered_text = self.rendered_text
        if self._prompt_pack is not None:
            self._render_prompt_pack()
            self.copy_status.set("已恢复上次生成的提示词包。")

    def selected_shot_ids(self) -> list[str]:
        return [shot_id for shot_id, selected in self.shot_selection.items() if selected.get()]

    def select_all_shots(self) -> None:
        for selected in self.shot_selection.values():
            selected.set(True)
        self._update_selected_button()

    def clear_shot_selection(self) -> None:
        for selected in self.shot_selection.values():
            selected.set(False)
        self._update_selected_button()

    def _update_selected_button(self) -> None:
        if hasattr(self, "generate_selected_button"):
            self.generate_selected_button.configure(state="normal" if self.selected_shot_ids() else "disabled")
            self.ai_selected_button.configure(state="normal" if self.selected_shot_ids() and not self._ai_running else "disabled")

    def _on_prompt_language_changed(self, _value: str) -> None:
        self.copy_status.set("语言已切换，请重新生成提示词。")

    def generate_all_prompt_pack(self) -> None:
        self._generate_prompt_pack(None)

    def generate_all_ai_prompt_pack(self) -> None:
        self._start_ai_generation(None)

    def generate_selected_ai_prompt_pack(self) -> None:
        shot_ids = self.selected_shot_ids()
        if not shot_ids:
            self.copy_status.set("请至少选择一个镜头。")
            return
        self._start_ai_generation(shot_ids)

    def regenerate_ai_shot_prompt_pack(self, shot_id: str) -> None:
        self._start_ai_generation([shot_id])

    def _start_ai_generation(self, shot_ids: list[str] | None) -> None:
        if self._ai_running:
            return
        artifact = self._result.artifact if self._result else None
        if not isinstance(artifact, StoryboardDraft):
            return
        try:
            api_key = load_api_key()
        except CredentialError:
            api_key = None
        if not api_key:
            self.copy_status.set("请先配置 DeepSeek API Key。")
            return
        self._ai_running = True
        self.ai_all_button.configure(state="disabled")
        self.ai_selected_button.configure(state="disabled")
        self.copy_status.set("DeepSeek AI 生成中…")
        model = "deepseek-v4-pro" if self.deepseek_model.get() == "V4 Pro" else DEFAULT_DEEPSEEK_MODEL
        threading.Thread(target=self._run_ai_generation, args=(artifact, shot_ids, api_key, model), daemon=True).start()

    def _run_ai_generation(self, storyboard: StoryboardDraft, shot_ids: list[str] | None, api_key: str, model: str) -> None:
        try:
            pack = self._ai_service_factory(api_key, model).generate(storyboard, shot_ids=shot_ids, output_language="en" if self.prompt_language.get() == "English" else "zh-CN")
        except Exception as exc:
            self.after(0, self._finish_ai_generation, None, self._deepseek_error_text(exc))
            return
        self.after(0, self._finish_ai_generation, pack, "")

    @staticmethod
    def _deepseek_error_text(error: Exception) -> str:
        if isinstance(error, AiPromptPackValidationError):
            return "DeepSeek 返回的提示词格式不完整。"
        if not isinstance(error, DeepSeekApiError):
            return "提示词处理失败。"
        status = getattr(error, "status_code", None)
        code = getattr(error, "error_code", None)
        messages = {401: "DeepSeek 认证失败，请检查 API Key。", 402: "DeepSeek API 余额不足，请充值后重试。", 400: "DeepSeek 请求格式错误。", 422: "DeepSeek 请求参数无效。", 429: "DeepSeek 请求过于频繁，请稍后重试。", 500: "DeepSeek 服务异常。", 503: "DeepSeek 服务繁忙。"}
        if status in messages: return messages[status]
        if code == "length_empty": return "DeepSeek 输出达到长度限制，未生成完整内容。"
        if code == "empty_content": return "DeepSeek 返回空内容，请重试。"
        if code == "timeout": return "DeepSeek 请求超时，请检查网络后重试。"
        if code == "connection": return "无法连接 DeepSeek API，请检查网络。"
        return "DeepSeek API 请求失败。"

    def _finish_ai_generation(self, pack: PromptPack | None, error_text: str = "") -> None:
        self._ai_running = False
        self.ai_all_button.configure(state="normal")
        self._update_selected_button()
        if pack is None:
            self.copy_status.set(f"{error_text or 'DeepSeek 生成失败。'}已保留原提示词。")
            return
        self.deepseek_model.set("V4 Pro" if pack.model == "deepseek-v4-pro" else "V4 Flash")
        self._prompt_pack = pack
        try:
            self._prompt_pack_store.save(pack)
        except OSError:
            self.copy_status.set("DeepSeek 提示词已生成，但自动保存失败。")
        else:
            self.copy_status.set("DeepSeek 提示词已生成并自动保存。")
        self._render_prompt_pack()

    def generate_selected_prompt_pack(self) -> None:
        shot_ids = self.selected_shot_ids()
        if not shot_ids:
            self.copy_status.set("请至少选择一个镜头。")
            return
        self._generate_prompt_pack(shot_ids)

    def regenerate_shot_prompt_pack(self, shot_id: str) -> None:
        self._generate_prompt_pack([shot_id])

    def _generate_prompt_pack(self, shot_ids: list[str] | None) -> None:
        artifact = self._result.artifact if self._result else None
        if not isinstance(artifact, StoryboardDraft):
            self.copy_status.set("No storyboard is available.")
            return
        self._prompt_pack = self._prompt_service.generate(artifact, shot_ids=shot_ids, output_language="en" if self.prompt_language.get() == "English" else "zh-CN")
        try:
            self._prompt_pack_store.save(self._prompt_pack)
        except OSError:
            self.copy_status.set("提示词包已生成，但自动保存失败。")
            self._render_prompt_pack()
            return
        self._render_prompt_pack()
        self.copy_status.set("提示词包已生成并自动保存。")

    def _render_prompt_pack(self) -> None:
        if not hasattr(self, "prompt_pack_section") or self._prompt_pack is None:
            return
        for child in self.prompt_pack_section.winfo_children():
            child.destroy()
        self._section_title(self.prompt_pack_section, "生产提示词包").grid(row=0, column=0, padx=12, pady=(8, 4), sticky="w")
        actions = ctk.CTkFrame(self.prompt_pack_section, fg_color="transparent")
        actions.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")
        PrimaryButton(actions, text="复制整个提示词包", width=140, command=lambda: self._copy(self._prompt_pack_text())).pack(side="left")
        SecondaryButton(actions, text="保存提示词包 JSON", width=158, command=self._save_prompt_pack_json).pack(side="left", padx=6)
        for index, prompt_shot in enumerate(self._prompt_pack.shots, start=2):
            # SoftCard uses placed decorative layers and is intentionally avoided here:
            # a prompt shot must grow to fit every field and its copy actions.
            card = ctk.CTkFrame(
                self.prompt_pack_section,
                fg_color=CARD_BACKGROUND,
                border_width=1,
                border_color=CARD_BORDER,
                corner_radius=RADIUS_CARD,
            )
            card.grid(row=index, column=0, padx=12, pady=6, sticky="ew")
            card.grid_columnconfigure(0, weight=1)
            card.grid_propagate(True)
            ctk.CTkLabel(card, text=f"SHOT {prompt_shot.sequence:03d}", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
            fields = [("首帧提示词", prompt_shot.first_frame_prompt), ("尾帧提示词", prompt_shot.end_frame_prompt), ("视频提示词", prompt_shot.video_prompt), ("负面提示词", prompt_shot.negative_prompt), ("连续性要求", prompt_shot.continuity_notes)]
            for field_row, (name, value) in enumerate(fields, start=1):
                field_frame = ctk.CTkFrame(card, fg_color="transparent")
                field_frame.grid(row=field_row, column=0, padx=16, pady=6, sticky="ew")
                field_frame.grid_columnconfigure(0, weight=1)
                field_frame.grid_propagate(True)
                ctk.CTkLabel(field_frame, text=name, font=ctk.CTkFont(size=14, weight="bold"), anchor="w").grid(row=0, column=0, sticky="ew")
                ctk.CTkLabel(field_frame, text=value, justify="left", anchor="w", wraplength=760).grid(row=1, column=0, pady=(2, 5), sticky="ew")
                SecondaryButton(field_frame, text="复制", width=70, command=lambda text=value: self._copy(text)).grid(row=2, column=0, sticky="w")
            card_actions = ctk.CTkFrame(card, fg_color="transparent")
            card_actions.grid(row=len(fields) + 1, column=0, padx=16, pady=(8, 12), sticky="w")
            card_actions.grid_propagate(True)
            PrimaryButton(card_actions, text="复制本镜头全部提示词", width=140, command=lambda shot=prompt_shot: self._copy(self._prompt_shot_text(shot))).pack(side="left", padx=3)
            SecondaryButton(card_actions, text="复制平台版", width=104, command=lambda shot=prompt_shot: self._copy(self._platform_prompt_shot_text(shot))).pack(side="left", padx=3)
            SecondaryButton(card_actions, text="AI 重新生成本镜头", width=142, command=lambda shot_id=prompt_shot.shot_id: self.regenerate_ai_shot_prompt_pack(shot_id)).pack(side="left", padx=3)
            SecondaryButton(card_actions, text="重新生成本镜头提示词", width=140, command=lambda shot_id=prompt_shot.shot_id: self.regenerate_shot_prompt_pack(shot_id)).pack(side="left", padx=3)
        self.rendered_text = getattr(self, "_storyboard_rendered_text", self.rendered_text) + "\n\n" + self._prompt_pack_text()

    @staticmethod
    def _prompt_shot_text(shot) -> str:
        return f"SHOT {shot.sequence:03d}\n\n首帧提示词：\n{shot.first_frame_prompt}\n\n尾帧提示词：\n{shot.end_frame_prompt}\n\n视频提示词：\n{shot.video_prompt}\n\n负面提示词：\n{shot.negative_prompt}\n\n连续性要求：\n{shot.continuity_notes}"

    def _prompt_pack_text(self) -> str:
        return "\n\n".join(self._prompt_shot_text(shot) for shot in self._prompt_pack.shots) if self._prompt_pack else ""

    def _selected_target_platform(self) -> PromptTargetPlatform:
        labels = {
            "通用": PromptTargetPlatform.GENERIC,
            "可灵": PromptTargetPlatform.KLING,
            "即梦": PromptTargetPlatform.JIMENG,
            "Runway": PromptTargetPlatform.RUNWAY,
            "Veo": PromptTargetPlatform.VEO,
        }
        return labels[self.target_platform.get()]

    def _platform_prompt_shot_text(self, shot) -> str:
        """Format a temporary platform export; canonical PromptPack remains untouched."""
        export = adapt_prompt_shot(shot, self._selected_target_platform())
        negative = export.negative_prompt or "不建议用于该平台的视频 Prompt。"
        return (
            f"目标平台：{export.platform.value}\nSHOT：{export.shot_id}\n\n"
            f"【首帧参考】\n{export.first_frame_prompt}\n\n"
            f"【尾帧参考】\n{export.end_frame_prompt}\n\n"
            f"【视频提示词】\n{export.video_prompt}\n\n"
            f"【Negative】\n{negative}\n\n"
            f"【连续性参考】\n{export.continuity_notes}\n\n"
            f"【使用说明】\n{export.usage_notes}"
        )

    def _save_prompt_pack_json(self) -> None:
        if self._prompt_pack is None:
            return
        path = filedialog.asksaveasfilename(initialfile=f"prompt-pack-{self._prompt_pack.storyboard_id}.json", defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(self._prompt_pack.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            self.copy_status.set("Prompt Pack JSON save failed.")
            return
        self.copy_status.set("Prompt Pack JSON saved.")

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
