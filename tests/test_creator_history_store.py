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


def test_legacy_directory_migrates_and_new_record_uses_new_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    legacy = tmp_path / "AI-Video-Production-Verifier" / "creator_history"
    legacy.mkdir(parents=True)
    record = {"history_id": "same", "created_at": "2026-01-01T00:00:00+00:00", "idea": "旧", "style": None, "goal": None, "result": result().model_dump(mode="json")}
    (legacy / "same.json").write_text(json.dumps(record), encoding="utf-8")
    store = CreatorHistoryStore()
    assert [item["history_id"] for item in store.list_records()] == ["same"]
    assert (tmp_path / "AIVideoProductionVerifier" / "creator_history" / "same.json").is_file()
    created = store.save(idea="新", style=None, goal=None, result=result())
    assert (tmp_path / "AIVideoProductionVerifier" / "creator_history" / f"{created}.json").is_file()
