from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from creator_desktop.api_key_state import dialog_state, should_save_new_key
from creator_desktop.credentials import (
    CredentialError,
    clear_api_key,
    has_saved_api_key,
    save_api_key,
)


class ApiKeyDialog(ctk.CTkToplevel):
    """Credential editor that never places a saved key in a Tk variable."""

    def __init__(self, master: ctk.CTk, on_changed=None) -> None:
        super().__init__(master)
        self._on_changed = on_changed
        self._has_saved_key = False
        self.title("DeepSeek API 设置")
        self.geometry("560x300")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        ctk.CTkLabel(self, text="DeepSeek API Key", font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=24, pady=(24, 8), anchor="w"
        )
        self.status_label = ctk.CTkLabel(self, text="", anchor="w")
        self.status_label.pack(padx=24, pady=(0, 4), anchor="w")
        # This entry is intentionally new and blank even when a key exists.
        self.key_entry = ctk.CTkEntry(self, show="•", width=500)
        self.key_entry.pack(padx=24, pady=6)
        self.help_label = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=500)
        self.help_label.pack(padx=24, pady=(0, 4), anchor="w")
        self.show_value = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self, text="显示API Key", variable=self.show_value, command=self._toggle_visible
        ).pack(padx=24, pady=4, anchor="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(padx=24, pady=14, fill="x")
        self.save_button = ctk.CTkButton(buttons, text="保存", command=self._save)
        self.save_button.pack(side="left")
        ctk.CTkButton(buttons, text="清除", command=self._clear, fg_color="#8b3a3a").pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="跳过并使用本地模式", command=self.destroy).pack(side="right")
        self._refresh_state()

    def _refresh_state(self) -> None:
        try:
            state = dialog_state(has_saved_api_key())
        except CredentialError:
            state = dialog_state(False)
        self._has_saved_key = state.has_saved_key
        self.status_label.configure(text=state.status_text, text_color=state.status_color)
        self.help_label.configure(text=state.help_text)
        self.save_button.configure(text=state.save_button_text)

    def _toggle_visible(self) -> None:
        # It only changes visibility for the newly typed entry content.
        self.key_entry.configure(show="" if self.show_value.get() else "•")

    def _save(self) -> None:
        new_key = self.key_entry.get().strip()
        if not should_save_new_key(new_key):
            messagebox.showinfo(
                "API Key",
                dialog_state(self._has_saved_key).empty_save_notice(),
                parent=self,
            )
            return
        try:
            save_api_key(new_key)
        except CredentialError as exc:
            messagebox.showerror("无法保存", str(exc), parent=self)
            return
        self.key_entry.delete(0, "end")
        self._refresh_state()
        if self._on_changed:
            self._on_changed()
        messagebox.showinfo("API Key", "API Key已安全保存。", parent=self)

    def _clear(self) -> None:
        if not self._has_saved_key:
            messagebox.showinfo("API Key", "当前没有已保存的API Key。", parent=self)
            return
        self._show_clear_confirmation()

    def _show_clear_confirmation(self) -> None:
        confirmation = ctk.CTkToplevel(self)
        confirmation.title("确认清除API Key")
        confirmation.geometry("460x180")
        confirmation.resizable(False, False)
        confirmation.transient(self)
        confirmation.grab_set()
        ctk.CTkLabel(
            confirmation,
            text="确定要清除已保存的DeepSeek API Key吗？\n清除后语义审计将不可用，但本地硬规则仍可使用。",
            justify="left",
            wraplength=410,
        ).pack(padx=24, pady=(28, 16))
        buttons = ctk.CTkFrame(confirmation, fg_color="transparent")
        buttons.pack(padx=24, pady=4, fill="x")
        ctk.CTkButton(
            buttons,
            text="确认清除",
            fg_color="#8b3a3a",
            command=lambda: self._confirm_clear(confirmation),
        ).pack(side="left")
        ctk.CTkButton(buttons, text="取消", command=confirmation.destroy).pack(side="right")

    def _confirm_clear(self, confirmation: ctk.CTkToplevel) -> None:
        try:
            clear_api_key()
        except CredentialError as exc:
            messagebox.showerror("无法清除", str(exc), parent=self)
            return
        confirmation.destroy()
        self.key_entry.delete(0, "end")
        self._refresh_state()
        if self._on_changed:
            self._on_changed()
        messagebox.showinfo("API Key", "已清除保存的API Key。", parent=self)
