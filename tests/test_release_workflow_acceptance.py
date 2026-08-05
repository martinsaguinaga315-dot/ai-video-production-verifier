from pathlib import Path


WORKFLOW = Path(".github/workflows/release-windows.yml")


def _acceptance_step(workflow: str) -> str:
    start = workflow.index("- name: Run Windows Release acceptance gate")
    end = workflow.index("- name: Publish GitHub Release assets", start)
    return workflow[start:end]


def test_release_workflow_runs_windows_acceptance_before_publishing_assets():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    acceptance = _acceptance_step(workflow)
    assert "powershell.exe" in acceptance
    assert "scripts/verify_windows_release.ps1" in acceptance
    for argument in ("-ReleaseDirectory release", "-ExpectedVersion", "-ExpectedCommit", "-SkipHistoryCheck", "-SkipInstalledAppCheck"):
        assert argument in acceptance
    assert "${{ env.VERSION }}" in acceptance
    assert "${{ github.sha }}" in acceptance
    assert "continue-on-error" not in acceptance
    assert "-HistoryDirectory" not in acceptance
    assert "-InstalledExecutable" not in acceptance
    assert "-LaunchInstalledApp" not in acceptance
    assert workflow.index("Run Windows Release acceptance gate") < workflow.index("Publish GitHub Release assets")


def test_release_workflow_keeps_one_version_source_and_no_release_gate_bypass():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "from app_version import VERSION" in workflow
    assert "v0.3.1" not in workflow
    assert "continue-on-error: true" not in workflow
    assert "if: always()" not in _acceptance_step(workflow)
