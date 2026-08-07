from types import SimpleNamespace

import tkinter as tk

import customtkinter as ctk
import pytest

from creator_desktop.mode_switcher import MODE_AI, MODE_CREATOR, MODE_OPTIONS, MODE_PROFESSIONAL, ModeSwitcher


@pytest.fixture
def root():
    try:
        app = ctk.CTk()
    except tk.TclError:
        pytest.skip("CustomTkinter requires an available display")
    app.geometry("900x600")
    app.deiconify()
    app.update_idletasks()
    yield app
    app.destroy()


def test_default_mode_and_menu_definition_are_ai_first():
    assert MODE_OPTIONS[0][0] == MODE_AI
    assert len(MODE_OPTIONS) == 3
    assert {item[0] for item in MODE_OPTIONS} == {MODE_AI, MODE_CREATOR, MODE_PROFESSIONAL}


def test_selection_updates_mode_closes_menu_and_calls_callback():
    calls = []
    switcher = SimpleNamespace(current_mode=MODE_AI, is_open=True, _on_change=calls.append)
    switcher.close_menu = lambda: setattr(switcher, "is_open", False)
    ModeSwitcher.select(switcher, MODE_PROFESSIONAL)
    assert switcher.current_mode == MODE_PROFESSIONAL and switcher.is_open is False
    assert calls == [MODE_PROFESSIONAL]


def test_selecting_current_mode_closes_menu_and_calls_callback():
    calls = []
    switcher = SimpleNamespace(current_mode=MODE_AI, is_open=True, _on_change=calls.append)
    switcher.close_menu = lambda: setattr(switcher, "is_open", False)
    ModeSwitcher.select(switcher, MODE_AI)
    assert switcher.is_open is False
    assert calls == [MODE_AI]


def test_open_menu_is_visible_sized_lifted_and_selectable(root):
    calls = []
    switcher = ModeSwitcher(root, calls.append)
    switcher.place(x=24, y=16)
    root.update_idletasks()

    switcher.toggle_menu()
    root.update_idletasks()
    menu = switcher._menu
    assert switcher.is_open is True
    assert menu is not None and menu.winfo_exists()
    assert menu.winfo_width() > 1 and menu.winfo_height() > 1
    assert menu.master is root
    assert root.winfo_children()[-1] is menu

    switcher.select(MODE_PROFESSIONAL)
    assert switcher.is_open is False
    assert switcher._menu is None
    assert calls == [MODE_PROFESSIONAL]


def test_toggle_menu_closes_an_open_menu(root):
    switcher = ModeSwitcher(root, lambda _mode: None)
    switcher.pack()
    root.update_idletasks()
    switcher.toggle_menu()
    switcher.toggle_menu()
    assert switcher.is_open is False
    assert switcher._menu is None
