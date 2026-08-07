import tkinter as tk
import customtkinter as ctk
import pytest
from creator_desktop.creator_history_store import CreatorHistoryStore
from creator_desktop.creator_history_view import CreatorHistoryView
from creator_desktop.ui_components import PrimaryButton
from story_generation.models import GenerationResult, GenerationStatus

@pytest.fixture
def root():
    try: app=ctk.CTk()
    except tk.TclError: pytest.skip("display unavailable")
    app.withdraw(); yield app; app.destroy()

def test_history_view_empty_and_records(root, tmp_path):
    store=CreatorHistoryStore(tmp_path); seen=[]; backs=[]
    view=CreatorHistoryView(root, store, seen.append, store.delete, lambda: backs.append(True)); view.pack()
    view._on_back()
    assert backs == [True]
    assert view.cget("fg_color") == "transparent"
    assert len(view.list_frame.winfo_children()) == 1
    history_id=store.save(idea="创意", style="风格", goal=None, result=GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft", artifact={"shots": []}))
    view.refresh(); assert len(view.list_frame.winfo_children()) == 1
    view._delete({"history_id": history_id}); assert store.list_records()==[]
    view.destroy()


def test_each_view_result_button_keeps_its_own_record(root, tmp_path):
    store = CreatorHistoryStore(tmp_path)
    selected = []
    for idea in ("记录 A", "记录 B", "记录 C"):
        store.save(idea=idea, style=None, goal=None, result=GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft", artifact={"shots": []}))
    view = CreatorHistoryView(root, store, selected.append, store.delete, lambda: None)
    view.pack(); root.update_idletasks()

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    buttons = [widget for widget in descendants(view.list_frame) if isinstance(widget, PrimaryButton)]
    expected = [record["history_id"] for record in store.list_records()]
    for button in buttons:
        button.invoke()
    assert [record["history_id"] for record in selected] == expected
    view.destroy()
