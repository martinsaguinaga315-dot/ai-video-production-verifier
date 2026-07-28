from __future__ import annotations

import customtkinter as ctk

from creator_desktop.main_window import MainWindow


def run() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = MainWindow()
    app.mainloop()
