from __future__ import annotations

from pathlib import Path

import desktop_app


def test_creator_smoke_argument_uses_smoke_entry_without_starting_desktop(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(desktop_app, "run_frozen_creator_smoke", lambda: calls.append("smoke") or 0)
    monkeypatch.setattr(desktop_app, "run", lambda: calls.append("desktop"))

    assert desktop_app.main(["--smoke-creator-ui"]) == 0
    assert calls == ["smoke"]


def test_normal_desktop_entry_remains_unchanged(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(desktop_app, "run", lambda: calls.append("desktop"))
    monkeypatch.setattr(desktop_app, "run_frozen_creator_smoke", lambda: calls.append("smoke") or 0)

    assert desktop_app.main([]) == 0
    assert calls == ["desktop"]


def test_frozen_creator_smoke_is_static_and_network_free() -> None:
    smoke = Path("creator_desktop/frozen_creator_smoke.py").read_text(encoding="utf-8")
    assert "from creator_desktop.creator_generation_view import CreatorGenerationView" in smoke
    assert "from creator_desktop.creator_generation_result import CreatorGenerationResultFrame" in smoke
    assert "from creator_desktop.creator_history_store import CreatorHistoryStore" in smoke
    assert "from story_generation.factories.creator_pipeline_factory import build_creator_pipeline" in smoke
    assert "build_creator_pipeline()" in smoke
    assert "TemporaryDirectory" in smoke
    assert "generate_json" not in smoke
    assert "load_api_key" not in smoke


def test_release_gate_runs_frozen_executable_and_restores_local_appdata() -> None:
    script = Path("packaging/build_windows.ps1").read_text(encoding="utf-8")
    assert "function Invoke-FrozenCreatorSmoke" in script
    assert "Start-Process -FilePath $FrozenExe -ArgumentList '--smoke-creator-ui'" in script
    assert "-Wait -PassThru" in script
    assert "Frozen Creator smoke test failed with code" in script
    assert "$env:LOCALAPPDATA = $oldLocalAppData" in script
    assert "FROZEN_CREATOR_SMOKE_RESULT = OK" in script
    assert "Invoke-Checked $buildPython @('scripts\\smoke_frozen_creator_ui.py')" not in script
