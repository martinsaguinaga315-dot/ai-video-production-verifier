from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from creator_desktop.credentials import CredentialError, clear_api_key, save_api_key


class ApiKeyDialog(ctk.CTkToplevel):
    def __init__(self, master: ctk.CTk, on_saved=None) -> None:
        super().__init__(master)
        self._on_saved = on_saved
        self.title("DeepSeek API 设置")
        self.geometry("520x220")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text="DeepSeek API Key", font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=24, pady=(24, 8), anchor="w"
        )
        self.key_entry = ctk.CTkEntry(self, show="•", width=450)
        self.key_entry.pack(padx=24, pady=6)
        self.show_value = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self, text="显示API Key", variable=self.show_value, command=self._toggle_visible
        ).pack(padx=24, pady=4, anchor="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(padx=24, pady=14, fill="x")
        ctk.CTkButton(buttons, text="保存", command=self._save).pack(side="left")
        ctk.CTkButton(buttons, text="清除", command=self._clear, fg_color="#8b3a3a").pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="跳过并使用本地模式", command=self.destroy).pack(side="right")

    def _toggle_visible(self) -> None:
        self.key_entry.configure(show="" if self.show_value.get() else "•")

    def _save(self) -> None:
        try:
            save_api_key(self.key_entry.get())
        except CredentialError as exc:
            messagebox.showerror("无法保存", str(exc), parent=self)
            return
        if self._on_saved:
            self._on_saved()
        self.destroy()

    def _clear(self) -> None:
        try:
            clear_api_key()
        except CredentialError as exc:
            messagebox.showerror("无法清除", str(exc), parent=self)
            return
        self.key_entry.delete(0, "end")
