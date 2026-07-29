from __future__ import annotations

import customtkinter as ctk

from app_version import APP_NAME
from creator_desktop.app_paths import is_smoke_test, resource_path
from creator_desktop.main_window import MainWindow


def run() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = MainWindow()
    app.title(APP_NAME)
    icon_path = resource_path("assets", "app.ico")
    if icon_path.is_file():
        try:
            app.iconbitmap(default=str(icon_path))
        except Exception:
            # A non-Windows source run can still open without the .ico hook.
            pass
    if is_smoke_test():
        # The build check initializes the same window and resources, but never
        # opens an API dialog or performs a network request.
        app.withdraw()
        app.after(350, app.destroy)
    app.mainloop()
