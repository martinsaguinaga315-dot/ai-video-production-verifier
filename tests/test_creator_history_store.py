import json

from creator_desktop.creator_history_store import CreatorHistoryStore
from story_generation.models import GenerationResult, GenerationStatus


def result():
    return GenerationResult(status=GenerationStatus.SUCCEEDED, artifact_type="storyboard_draft", artifact={"shots": []})


def test_save_load_persists_and_excludes_api_key(tmp_path):
    store = CreatorHistoryStore(tmp_path)
    history_id = store.save(idea="创意", style=None, goal="目标", result=result())
    loaded = CreatorHistoryStore(tmp_path).load(history_id)
    assert loaded["idea"] == "创意" and loaded["history_id"] == history_id
    assert "api_key" not in json.dumps(loaded).lower()


def test_delete_clear_trim_and_corrupt_record_are_safe(tmp_path):
    store = CreatorHistoryStore(tmp_path, max_records=2)
    ids = [store.save(idea=str(index), style=None, goal=None, result=result()) for index in range(3)]
    assert len(store.list_records()) == 2
    store.delete(ids[-1]); assert len(store.list_records()) == 1
    (tmp_path / "broken.json").write_text("{bad", encoding="utf-8")
    assert len(store.list_records()) == 1
    store.clear(); assert store.list_records() == []
