"""Small, layout-friendly CustomTkinter components used by the creator UI."""
from __future__ import annotations

import customtkinter as ctk
from creator_desktop.ui_theme import (
    ACCENT, ACCENT_HOVER, CARD_BACKGROUND, CARD_BORDER, RADIUS_BUTTON,
    RADIUS_CARD, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)


class SoftCard(ctk.CTkFrame):
    """A single, geometry-safe card which keeps the historic ``content`` API."""
    def __init__(self, master, **kwargs):
        fixed_size = "width" in kwargs or "height" in kwargs
        kwargs.setdefault("fg_color", CARD_BACKGROUND)
        kwargs.setdefault("corner_radius", RADIUS_CARD)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", CARD_BORDER)
        super().__init__(master, **kwargs)
        # A placed surface with relheight=1 extended past dynamic cards and left
        # white redraw trails while a CTkScrollableFrame canvas moved underneath.
        # Keeping content as the card itself preserves every existing caller.
        self.content = self
        if fixed_size:
            # The former placed surface did not propagate child geometry. Preserve
            # explicit card dimensions (notably the 820px creation card) now that
            # children are direct descendants of this single-layer frame.
            self.grid_propagate(False)
            self.pack_propagate(False)


class PageScrollContainer(ctk.CTkScrollableFrame):
    """A page-level scroll viewport with an explicit refresh hook for dynamic rows."""
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

    def refresh_scroll_region(self) -> None:
        """Synchronize the canvas after a child is shown, hidden, or resized."""
        self.update_idletasks()
        canvas = self._parent_canvas
        canvas.configure(scrollregion=canvas.bbox("all"))


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
    def __init__(self, master, on_adjust=None, textvariable=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="制作设置", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12)).pack(side="left")
        self.summary_label = ctk.CTkLabel(self, textvariable=textvariable, text="60 秒 · 16:9 · 自动镜头 · 中文输出", text_color=TEXT_SECONDARY)
        self.summary_label.pack(side="left", padx=(8, 12))
        if on_adjust is not None:
            SecondaryButton(self, text="调整制作设置", width=118, command=on_adjust).pack(side="right")

    def set_summary(self, value: str) -> None:
        self.summary_label.configure(text=value)


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
