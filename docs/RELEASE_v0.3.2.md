# v0.3.2 Release Notes

Release date: 2026-08-06

## Overview

v0.3.2 unifies the desktop presentation of AI Creator, Standard Creator, and Professional JSON verification while preserving their established generation, analysis, verification, history, import, and export behavior.

## Unified three-mode desktop experience

- A single mode switcher and shared top toolbar provide consistent navigation, API status, history access, and settings.
- The stable light design uses warm white and pale blue-grey surfaces, solid white cards, restrained shadows, and shared button hierarchy.
- Standard Creator uses two desktop-width text-input cards for project requirements and director plans.
- Professional JSON uses distinct file-input, verification-control, status, and issue-list cards with a scrollable result area.
- In-page duplicate API status and API settings controls were removed; the top toolbar remains the single configuration entry point.

## Compatibility

- Generation, analysis, verification, import, export, and local history protocols are unchanged.
- API Key storage and use are unchanged.
- Creator history JSON format is unchanged.
- `GenerationResult`, `StoryboardDraft`, and verification-report formats are unchanged.

## Windows x64 distribution

This release is prepared for Windows x64 Setup and Portable distributions. Expected release assets are:

- `AI-Video-Production-Verifier-Setup-v0.3.2.exe`
- `AI-Video-Production-Verifier-Portable-v0.3.2.zip`
- `SHA256SUMS.txt`
- `release_manifest_v0.3.2.json`

Verify downloaded assets against `SHA256SUMS.txt`; the manifest version must be `0.3.2` and its `git_commit` must match the formal `v0.3.2` tag commit.

## API Key privacy

DeepSeek-related capabilities require a user-configured API Key. The application does not embed, display, or upload a user's API Key; existing secure storage behavior is unchanged.

## Known limitations

- The current desktop distribution primarily targets Windows x64.
- The stable light interface uses solid cards and does not use real-time system frosted-glass blur.
- DeepSeek-related capabilities require the user to configure an API Key.
- Some GUI tests may be skipped when no display is available.

## Verification and release acceptance

Run the full pytest suite, then run `scripts/verify_windows_release.ps1` against generated assets with expected version `0.3.2` and the release commit. The Release Windows workflow runs `release_gate` for pull requests and manual dry-runs; only a matching `v0.3.2` tag push can enter the publish job.
