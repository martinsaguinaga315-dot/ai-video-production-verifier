# AI Video Production Verifier v0.3.3

Release date: 2026-08-09

## Highlights

- Storyboards can now produce a reusable Production Prompt Pack for each shot.
- DeepSeek V4 Flash and V4 Pro can enhance selected or all shot prompts in a production-focused mode.
- Production prompts now include concrete cinematography execution, duration-aware motion, fact preservation, and continuity controls.
- Local platform adapters support Generic, Kling, Jimeng, Runway, and Veo without changing the saved canonical Prompt Pack.
- Prompt Packs are saved locally by storyboard and restored when that storyboard is opened again.

## Prompt Pack

Each Prompt Pack shot has six items: its Shot ID plus five production fields:

- First Frame: a directly generatable opening image specification.
- End Frame: a precise freeze-frame specification for the final state and handoff.
- Video: an ordered, duration-aware motion prompt.
- Negative: shot-specific constraints that prevent unwanted generation changes.
- Continuity: executable locks for identity, props, spatial layout, lighting, and the next-shot handoff.

The desktop UI supports generating all or selected shots, regenerating one shot, copying individual fields, copying a complete shot or the complete Prompt Pack, and exporting Prompt Packs as JSON.

## AI Prompt Generation

- Supports `deepseek-v4-flash` and `deepseek-v4-pro`.
- Uses a non-thinking production mode, JSON mode, an 8192-token request limit, and a safe single retry for empty content.
- Validates required fields and shot identity before accepting an AI result.
- Keeps the existing Prompt Pack when AI generation fails.

## Prompt Quality

Prompt generation emphasizes concrete cinematography execution details: composition, blocking, camera angle and height, lens feeling, depth of field, foreground/midground/background, lighting direction, color temperature, motion pacing, and focus behavior.

The prompt contract preserves storyboard facts and prohibits unsupported additions to characters, props, locations, wardrobe, story events, and environmental events. End frames are freeze-frame handoff specifications, and continuity notes lock the information needed by the next shot.

## Platform Adapters

The canonical Prompt Pack is the source of truth. Platform output is a local, temporary export and never overwrites saved Prompt Pack content.

- Generic
- Kling
- Jimeng
- Runway
- Veo

Kling, Jimeng, and Veo preserve canonical prompt fields verbatim while expressing platform-specific guidance through usage notes. For Runway Image-to-Video, Negative is not recommended for direct use in the video prompt.

## Stability and safety

- DeepSeek API errors, AI prompt validation errors, and local processing errors are classified separately.
- Malformed, empty, or incompatible AI responses are validated before use.
- API keys and Authorization values are not included in user-facing errors.
- `reasoning_content` is not persisted to Prompt Packs, history, JSON exports, UI, or logs.

## Verification

- pytest: 365 collected, 336 passed, 29 skipped, 0 failed.
- `git diff --check`: PASS.
- Creator UI smoke: PASS.
- Real DeepSeek validation: V4 Flash success, V4 Pro success, AI generation for a selected shot success, and AI generation for all shots success.
- Platform UI validation: Runway Negative behavior verified; model and target-platform selectors are independent.

## Windows x64 distribution

This release is prepared for Windows x64 Setup and Portable distributions. Expected release assets are:

- `AI-Video-Production-Verifier-Setup-v0.3.3.exe`
- `AI-Video-Production-Verifier-Portable-v0.3.3.zip`
- `SHA256SUMS.txt`
- `release_manifest_v0.3.3.json`

Verify downloaded assets against `SHA256SUMS.txt`; the manifest version must be `0.3.3` and its `git_commit` must match the formal `v0.3.3` tag commit. Run the full pytest suite, then run `scripts/verify_windows_release.ps1` against generated assets with expected version `0.3.3` and the release commit. The Release Windows workflow runs `release_gate` for pull requests and manual dry-runs; only a matching `v0.3.3` tag push can enter the publish job.
