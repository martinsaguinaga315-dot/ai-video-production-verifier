"""Stable, low-contrast warm background without image dependencies."""
from __future__ import annotations

import tkinter as tk

from creator_desktop.ui_theme import APP_BACKGROUND, APP_BACKGROUND_BOTTOM, APP_BACKGROUND_TOP


class AmbientBackground(tk.Canvas):
    """A few Canvas bands provide a quiet warm gradient without image rendering."""
    def __init__(self, master, **kwargs):
        super().__init__(master, highlightthickness=0, bd=0, bg=APP_BACKGROUND, **kwargs)
        self._resize_job = None
        self.bind("<Configure>", self._queue_redraw)

    def _queue_redraw(self, _event=None):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after_idle(self._redraw)

    def _redraw(self):
        self._resize_job = None
        width, height = self.winfo_width(), self.winfo_height()
        if width < 2 or height < 2:
            return
        self.delete("gradient")
        colors = (APP_BACKGROUND_TOP, APP_BACKGROUND, APP_BACKGROUND_BOTTOM)
        band_height = max(1, height // len(colors))
        for index, color in enumerate(colors):
            self.create_rectangle(0, index * band_height, width, height if index == len(colors) - 1 else (index + 1) * band_height, fill=color, outline="", tags="gradient")
