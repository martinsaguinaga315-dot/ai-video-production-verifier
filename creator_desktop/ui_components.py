"""Small, layout-friendly CustomTkinter components used by the creator UI."""
from __future__ import annotations

import customtkinter as ctk
from creator_desktop.ui_theme import (
    ACCENT, ACCENT_HOVER, CARD_BACKGROUND, CARD_BORDER, CARD_SHADOW, RADIUS_BUTTON,
    RADIUS_CARD, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)


class SoftCard(ctk.CTkFrame):
    """Stable two-layer card: a restrained offset shadow and white content surface."""
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.shadow = ctk.CTkFrame(self, fg_color=CARD_SHADOW, corner_radius=RADIUS_CARD)
        self.shadow.place(x=0, y=6, relwidth=1, relheight=1)
        self.surface = ctk.CTkFrame(self, fg_color=CARD_BACKGROUND, corner_radius=RADIUS_CARD, border_width=1, border_color=CARD_BORDER)
        self.surface.place(x=0, y=0, relwidth=1, relheight=1)
        self.content = self.surface


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", ACCENT)
        kwargs.setdefault("hover_color", ACCENT_HOVER)
        kwargs.setdefault("corner_radius", RADIUS_BUTTON)
        kwargs.setdefault("height", 42)
        super().__init__(master, **kwargs)


class SecondaryButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", CARD_BACKGROUND)
        kwargs.setdefault("hover_color", "#F0F2F7")
        kwargs.setdefault("text_color", TEXT_PRIMARY)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", CARD_BORDER)
        kwargs.setdefault("corner_radius", RADIUS_BUTTON)
        kwargs.setdefault("height", 38)
        super().__init__(master, **kwargs)


class StatusText(ctk.CTkLabel):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("text_color", TEXT_SECONDARY)
        kwargs.setdefault("font", ctk.CTkFont(size=12))
        super().__init__(master, **kwargs)


class PageTitle(ctk.CTkLabel):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("text_color", TEXT_PRIMARY)
        kwargs.setdefault("font", ctk.CTkFont(size=32, weight="bold"))
        super().__init__(master, **kwargs)


class SettingsSummary(ctk.CTkFrame):
    def __init__(self, master, on_adjust=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="制作设置", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkLabel(self, text="15 秒 · 16:9 · 自动镜头 · 中文输出", text_color=TEXT_SECONDARY).pack(side="left", padx=(8, 12))
        if on_adjust is not None:
            SecondaryButton(self, text="调整制作设置", width=118, command=on_adjust).pack(side="right")


class RecentProjectRow(SoftCard):
    def __init__(self, master, title: str, detail: str = "继续最近项目", command=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title_label = ctk.CTkLabel(self.content, text=title, text_color=TEXT_PRIMARY, anchor="w")
        self.title_label.pack(side="left", padx=16, pady=12, fill="x", expand=True)
        self.detail_label = ctk.CTkLabel(self.content, text=detail, text_color=TEXT_SECONDARY)
        self.detail_label.pack(side="right", padx=16)
        if command:
            self.bind("<Button-1>", lambda _event: command())
            self.title_label.bind("<Button-1>", lambda _event: command())
