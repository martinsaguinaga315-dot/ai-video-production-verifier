import tkinter as tk
import customtkinter as ctk
import pytest
from creator_desktop.creator_history_store import CreatorHistoryStore
from creator_desktop.creator_history_view import CreatorHistoryView
from story_generation.models import GenerationResult, GenerationStatus

@pytest.fixture
def root():
    try: app=ctk.CTk()
    except tk.TclError: pytest.skip("display unavailable")
    app.withdraw(); yield app; app.destroy()

def test_history_view_empty_and_records(root, tmp_path):
    store=CreatorHistoryStore(tmp_path); seen=[]
    view=CreatorHistoryView(root, store, seen.append, store.delete); view.pack()
    assert len(view.list_frame.winfo_children()) == 1
    history_id=store.save(idea="创意", style="风格", goal=None, result=GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft", artifact={"shots": []}))
    view.refresh(); assert len(view.list_frame.winfo_children()) == 1
    view._delete({"history_id": history_id}); assert store.list_records()==[]
    view.destroy()
