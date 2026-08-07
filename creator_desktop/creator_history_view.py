from __future__ import annotations

import customtkinter as ctk

from creator_desktop.ui_components import PageTitle, PrimaryButton, SecondaryButton, SoftCard
from creator_desktop.ui_theme import MAIN_CONTENT_WIDE, PAGE_GUTTER, TEXT_MUTED, TEXT_SECONDARY


class CreatorHistoryView(ctk.CTkFrame):
    def __init__(self, master, store, on_view, on_delete, on_back) -> None:
        super().__init__(master, fg_color="transparent")
        self.store, self._on_view, self._on_delete = store, on_view, on_delete
        self._on_back = on_back
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(0, weight=1)
        content = ctk.CTkFrame(self, fg_color="transparent", width=MAIN_CONTENT_WIDE)
        content.grid(row=0, column=0, padx=PAGE_GUTTER, pady=(12, 18), sticky="nsew")
        content.grid_columnconfigure(0, weight=1); content.grid_rowconfigure(1, weight=1)
        controls = ctk.CTkFrame(content, fg_color="transparent"); controls.grid(row=0, column=0, pady=(10, 14), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        title_area = ctk.CTkFrame(controls, fg_color="transparent")
        title_area.grid(row=0, column=0, sticky="w")
        PageTitle(title_area, text="生成历史").pack(anchor="w")
        ctk.CTkLabel(title_area, text="查看、恢复或管理过去的 AI 创作结果", text_color=TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))
        actions = ctk.CTkFrame(controls, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")
        SecondaryButton(actions, text="返回 AI 创作", width=128, command=self._on_back).pack(side="left", padx=4)
        SecondaryButton(actions, text="刷新", width=76, command=self.refresh).pack(side="left", padx=4)
        SecondaryButton(actions, text="清空全部", width=92, command=self._clear).pack(side="left", padx=4)
        self.list_frame = ctk.CTkScrollableFrame(content, fg_color="transparent"); self.list_frame.grid(row=1, column=0, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1); self.refresh()

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children(): child.destroy()
        records = self.store.list_records()
        if not records:
            empty = SoftCard(self.list_frame, height=160)
            empty.grid(row=0, column=0, padx=4, pady=42, sticky="ew")
            ctk.CTkLabel(empty.content, text="暂无生成历史", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(38, 4))
            ctk.CTkLabel(empty.content, text="完成一次 AI 创作后，结果会自动保存在这里。", text_color=TEXT_MUTED).pack()
            return
        for index, record in enumerate(records):
            result = record.get("result", {}); artifact = result.get("artifact") or {}; metadata = result.get("metadata") or {}
            row = SoftCard(self.list_frame)
            row.grid(row=index, column=0, padx=4, pady=7, sticky="ew"); row.content.grid_columnconfigure(0, weight=1)
            idea = record.get("idea", "")[:120] or "未命名创意"
            details = f"创建时间：{record.get('created_at', '未提供')}\n风格：{record.get('style') or '未指定'}  ·  状态：{result.get('status', 'unknown')}\n镜头数量：{len(artifact.get('shots', []))}  ·  目标时长：{artifact.get('target_duration_s', '未提供')}  ·  AI 修正次数：{metadata.get('repair_count', 0)}"
            ctk.CTkLabel(row.content, text=idea, font=ctk.CTkFont(size=16, weight="bold"), anchor="w").grid(row=0, column=0, padx=18, pady=(15, 4), sticky="ew")
            ctk.CTkLabel(row.content, text=details, justify="left", text_color=TEXT_SECONDARY, wraplength=780, anchor="w").grid(row=1, column=0, padx=18, pady=(0, 15), sticky="w")
            actions = ctk.CTkFrame(row.content, fg_color="transparent")
            actions.grid(row=0, column=1, rowspan=2, padx=18, pady=16, sticky="e")
            PrimaryButton(actions, text="查看结果", width=100, command=lambda item=record: self._on_view(item)).pack(side="left", padx=4)
            SecondaryButton(actions, text="删除", width=70, command=lambda item=record: self._delete(item)).pack(side="left", padx=4)

    def _delete(self, record) -> None:
        self._on_delete(record["history_id"]); self.refresh()

    def _clear(self) -> None:
        self.store.clear(); self.refresh()
