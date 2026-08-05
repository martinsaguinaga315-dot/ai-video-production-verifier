from pathlib import Path


WORKFLOW = Path(".github/workflows/release-windows.yml")


def _acceptance_step(workflow: str) -> str:
    start = workflow.index("- name: Run Windows Release acceptance gate")
    end = workflow.index("- name: Publish GitHub Release assets", start)
    return workflow[start:end]


def _publish_job(workflow: str) -> str:
    return workflow[workflow.index("  publish:"):]


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
    assert workflow.index("- name: Run Windows Release acceptance gate") < workflow.index("- name: Publish GitHub Release assets")


def test_release_workflow_keeps_one_version_source_and_no_release_gate_bypass():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "from app_version import VERSION" in workflow
    assert "v0.3.1" not in workflow
    assert "continue-on-error: true" not in workflow
    assert "if: always()" not in _acceptance_step(workflow)


def test_manual_dispatch_and_pull_request_are_safe_dry_runs():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    publish = _publish_job(workflow)
    assert "workflow_dispatch:" in workflow
    assert "publish_release:" not in workflow
    assert "pull_request:" in workflow
    assert "branches: [main]" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "dry-run" in workflow
    assert "needs: release_gate" in publish
    assert "github.event_name == 'push'" in publish
    assert "github.ref_type == 'tag'" in publish
    assert "startsWith(github.ref_name, 'v')" in publish
    assert "workflow_dispatch" not in publish
    assert "pull_request" not in publish
    assert "inputs." not in publish
    assert "if: always()" not in publish


def test_dry_run_release_gate_stays_read_only_and_does_not_leak_token():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    acceptance = _acceptance_step(workflow)
    gate = workflow[workflow.index("  release_gate:"):workflow.index("  publish:")]
    assert "contents: read" in workflow
    assert "contents: write" in _publish_job(workflow)
    assert "pull_request_target" not in workflow
    assert "github.token" not in acceptance
    assert "secrets." not in acceptance
    assert "continue-on-error" not in acceptance
    assert workflow.index("Run Windows Release acceptance gate") < workflow.index("Upload verified Windows build artifact")


def test_publish_consumes_verified_artifact_without_rebuilding():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    gate = workflow[workflow.index("  release_gate:"):workflow.index("  publish:")]
    publish = _publish_job(workflow)
    assert "softprops/action-gh-release@v2" not in gate
    assert publish.count("softprops/action-gh-release@v2") == 1
    assert "actions/download-artifact@v4" in publish
    assert "build_windows.ps1" not in publish
