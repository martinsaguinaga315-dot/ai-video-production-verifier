# v0.3.1 Release Notes

Release type: Windows Release acceptance and publishing-safety update.

## Highlights

- Windows Release automatic acceptance script.
- Setup and Portable SHA256 verification.
- Release Manifest version and git commit verification.
- Portable ZIP structure verification.
- UTF-8 Chinese Creator history JSON validation and API Key leakage scanning.
- GitHub Release pre-publication acceptance gate.
- Pull Request and `workflow_dispatch` safe dry-runs.
- Separate `release_gate` read permission and `publish` write permission jobs.
- Only `v*` tag pushes can publish a formal GitHub Release.

## Verification

- Local full pytest passed.
- Windows PowerShell 5.1 acceptance behavior was verified.
- GitHub Windows Runner dry-run for PR #1 completed: `release_gate` succeeded, `publish` was skipped, and `windows-release-dry-run-v0.3.0` was generated.
- The successful gate log contained `RELEASE_ACCEPTANCE_RESULT = OK`.

After this version bump, the next PR dry-run is expected to generate `windows-release-dry-run-v0.3.1`.

## Upgrade notes

- Creator history JSON format is unchanged.
- API Key storage strategy is unchanged.
- Installation directory rules are unchanged.
- Existing Creator functionality is unchanged.
- v0.3.1 can be installed over v0.3.0.

## Release assets

- `AI-Video-Production-Verifier-Setup-v0.3.1.exe`
- `AI-Video-Production-Verifier-Portable-v0.3.1.zip`
- `SHA256SUMS.txt`
- `release_manifest_v0.3.1.json`

## Security notes

- After downloading, verify assets against `SHA256SUMS.txt`.
- The Manifest `git_commit` must match the formal release tag commit.
- A GitHub Actions dry-run artifact is not a formal GitHub Release.
