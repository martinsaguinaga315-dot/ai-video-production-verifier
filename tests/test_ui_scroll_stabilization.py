import tkinter as tk

import customtkinter as ctk
import pytest

from creator_desktop.ui_components import PageScrollContainer, SoftCard


@pytest.fixture(scope="module")
def root():
    try:
        app = ctk.CTk()
    except tk.TclError:
        pytest.skip("CustomTkinter requires an available display")
    app.withdraw()
    yield app
    app.destroy()


def test_soft_card_is_single_layer_and_keeps_content_api(root):
    card = SoftCard(root, width=300, height=120)

    assert card.content is card
    assert card.winfo_children() == []

    card.destroy()


def test_page_scroll_container_refreshes_canvas_region(root):
    page = PageScrollContainer(root, width=300, height=120)
    ctk.CTkFrame(page, height=480).grid(row=0, column=0)
    page.refresh_scroll_region()

    assert page._parent_canvas.cget("scrollregion")

    page.destroy()
