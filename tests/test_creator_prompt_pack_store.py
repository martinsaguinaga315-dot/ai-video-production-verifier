from creator_desktop.creator_prompt_pack_store import CreatorPromptPackStore
from story_generation.models import PromptPack, PromptPackShot


def prompt_pack(language="zh-CN"):
    return PromptPack(
        prompt_pack_id="pack-original", storyboard_id="storyboard-001", storyboard_version=1,
        generation_target="generic", output_language=language,
        shots=[PromptPackShot(shot_id="shot-001", scene_id="scene-001", sequence=1,
                              first_frame_prompt="中文首帧", end_frame_prompt="中文尾帧",
                              video_prompt="中文视频", negative_prompt="中文负面", continuity_notes="中文连续性")],
    )


def test_save_load_round_trip_preserves_utf8_and_pack_metadata(tmp_path):
    store = CreatorPromptPackStore(tmp_path)
    original = prompt_pack("en")
    path = store.save(original)
    loaded = store.load("storyboard-001")
    assert path.name == "storyboard-001.json"
    assert loaded == original
    assert "中文首帧" in path.read_text(encoding="utf-8")
    assert store.exists("storyboard-001")


def test_missing_or_corrupt_pack_is_ignored(tmp_path):
    store = CreatorPromptPackStore(tmp_path)
    assert store.load("missing") is None
    (tmp_path / "broken.json").write_text("{bad", encoding="utf-8")
    assert store.load("broken") is None


def test_new_save_atomically_overwrites_latest_pack(tmp_path):
    store = CreatorPromptPackStore(tmp_path)
    first, latest = prompt_pack(), prompt_pack("en")
    first.prompt_pack_id = "pack-first"
    latest.prompt_pack_id = "pack-latest"
    store.save(first); store.save(latest)
    assert store.load("storyboard-001").prompt_pack_id == "pack-latest"
    assert not list(tmp_path.glob("*.tmp"))
