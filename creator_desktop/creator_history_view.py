from __future__ import annotations

import customtkinter as ctk


class CreatorHistoryView(ctk.CTkFrame):
    def __init__(self, master, store, on_view, on_delete) -> None:
        super().__init__(master)
        self.store, self._on_view, self._on_delete = store, on_view, on_delete
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        controls = ctk.CTkFrame(self, fg_color="transparent"); controls.grid(row=0, column=0, padx=20, pady=12, sticky="ew")
        ctk.CTkLabel(controls, text="生成历史", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        ctk.CTkButton(controls, text="刷新", command=self.refresh).pack(side="right")
        ctk.CTkButton(controls, text="清空全部", command=self._clear).pack(side="right", padx=6)
        self.list_frame = ctk.CTkScrollableFrame(self); self.list_frame.grid(row=1, column=0, padx=20, pady=(0, 16), sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1); self.refresh()

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children(): child.destroy()
        records = self.store.list_records()
        if not records:
            ctk.CTkLabel(self.list_frame, text="暂无生成历史").grid(row=0, column=0, padx=12, pady=24, sticky="w")
            return
        for index, record in enumerate(records):
            result = record.get("result", {}); artifact = result.get("artifact") or {}; metadata = result.get("metadata") or {}
            text = f"{record['created_at']}\n{record.get('idea', '')[:80]}\n风格：{record.get('style') or '未指定'}｜状态：{result.get('status', 'unknown')}｜镜头：{len(artifact.get('shots', []))}｜时长：{artifact.get('target_duration_s', '未提供')}｜修正：{metadata.get('repair_count', 0)}"
            row = ctk.CTkFrame(self.list_frame); row.grid(row=index, column=0, padx=8, pady=6, sticky="ew"); row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=text, justify="left", wraplength=650).grid(row=0, column=0, padx=10, pady=10, sticky="w")
            ctk.CTkButton(row, text="查看结果", width=82, command=lambda item=record: self._on_view(item)).grid(row=0, column=1, padx=4)
            ctk.CTkButton(row, text="删除", width=60, command=lambda item=record: self._delete(item)).grid(row=0, column=2, padx=8)

    def _delete(self, record) -> None:
        self._on_delete(record["history_id"]); self.refresh()

    def _clear(self) -> None:
        self.store.clear(); self.refresh()
