"""Single-button mode selector with a lightweight in-window popover."""
from __future__ import annotations

from typing import Callable
import customtkinter as ctk

from creator_desktop.ui_components import SecondaryButton
from creator_desktop.ui_theme import ACCENT_SOFT, CARD_BACKGROUND, CARD_BORDER, CARD_SHADOW, RADIUS_MENU, TEXT_PRIMARY, TEXT_SECONDARY

MODE_AI = "AI 创作模式"
MODE_CREATOR = "普通创作模式"
MODE_PROFESSIONAL = "专业 JSON 模式"
MODE_OPTIONS = (
    (MODE_AI, "AI 创作生成", "智能生成分镜与镜头方案"),
    (MODE_CREATOR, "普通创作者模式", "自主创作分镜与脚本内容"),
    (MODE_PROFESSIONAL, "专业JSON模式", "以结构化数据精确控制作品"),
)


class ModeSwitcher(ctk.CTkFrame):
    def __init__(self, master, on_change: Callable[[str], None], **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._on_change = on_change
        self.current_mode = MODE_AI
        self.is_open = False
        self._button = SecondaryButton(self, text="", width=184, height=42, fg_color=CARD_BACKGROUND, hover_color=ACCENT_SOFT, border_color=CARD_BORDER, corner_radius=21, command=self.toggle_menu)
        self._button.pack()
        self._menu = None
        self._update_button()

    def _update_button(self):
        self._button.configure(text=f"{self.current_mode}  {'⌃' if self.is_open else '⌄'}")

    def toggle_menu(self):
        if self.is_open:
            self.close_menu()
        else:
            self.open_menu()

    def open_menu(self):
        if self.is_open:
            return
        self.is_open = True
        self._update_button()
        # The switcher itself is only as tall as its button in the header grid.
        # Put the popover on the toplevel so neither that grid cell nor a page
        # canvas can clip it.
        self._menu = ctk.CTkFrame(
            self.winfo_toplevel(),
            width=300,
            fg_color=CARD_BACKGROUND,
            corner_radius=RADIUS_MENU,
            border_width=1,
            border_color=CARD_BORDER,
        )
        menu = self._menu
        for display, _internal, description in MODE_OPTIONS:
            selected = display == self.current_mode
            row = ctk.CTkFrame(menu, fg_color=ACCENT_SOFT if selected else "transparent", corner_radius=14)
            row.pack(fill="x", padx=8, pady=4)
            label = ctk.CTkLabel(row, text=f"{display}{'  ✓' if selected else ''}", text_color=TEXT_PRIMARY, anchor="w")
            label.pack(fill="x", padx=12, pady=(8, 0))
            detail = ctk.CTkLabel(row, text=description, text_color=TEXT_SECONDARY, font=ctk.CTkFont(size=12), anchor="w")
            detail.pack(fill="x", padx=12, pady=(0, 8))
            for widget in (row, label, detail):
                widget.bind("<Button-1>", lambda _event, mode=display: self.select(mode))
        self._position_menu()
        self._menu.lift()

    def _position_menu(self) -> None:
        """Place the root-level popover directly beneath the mode button."""
        root = self.winfo_toplevel()
        root.update_idletasks()
        x = self._button.winfo_rootx() - root.winfo_rootx()
        y = self._button.winfo_rooty() - root.winfo_rooty() + self._button.winfo_height() + 6
        self._menu.place(x=x, y=y)
        self._menu.update_idletasks()

    def close_menu(self):
        if self._menu is not None:
            self._menu.destroy()
            self._menu = None
        self.is_open = False
        self._update_button()

    def select(self, mode: str):
        changed = mode != self.current_mode
        self.current_mode = mode
        self.close_menu()
        if changed:
            self._on_change(mode)
