# Changelog

All notable changes to this project are documented here.

## v0.3.3

Release date: 2026-08-09

### Added

- Added Production Prompt Packs for every storyboard shot: first-frame prompt, end-frame prompt, video prompt, negative prompt, and continuity requirements.
- Added local Prompt Pack generation for all shots or selected shots, per-field copying, full-shot and full-pack copying, per-shot regeneration, and JSON export.
- Added Prompt Pack persistence by storyboard, preserving provider, model, output language, and prompt content for later restoration.
- Added DeepSeek AI Prompt generation with `deepseek-v4-flash` and `deepseek-v4-pro`.
- Added local platform prompt adapters for Generic, Kling, Jimeng, Runway, and Veo. Platform exports do not overwrite the canonical Prompt Pack.

### Improved

- Strengthened production-prompt execution detail for composition, blocking, camera angle and height, lens feeling, depth of field, foreground/midground/background, lighting direction, color temperature, motion pacing, and focus behavior.
- Improved first-frame and end-frame consistency; end frames are now specified as precise freeze-frame handoff states.
- Added shot-specific negative constraints and continuity locks for identity, props, layout, lighting, action end states, and next-shot handoff.
- Strengthened fact preservation so AI prompt enhancement does not invent unprovided characters, props, locations, wardrobe, story events, or environmental events.
- Improved platform guidance: Kling, Jimeng, and Veo retain canonical field fidelity, while Runway keeps Negative out of its video-prompt workflow.

### Fixed

- Prompt Pack requests now explicitly use non-thinking mode, JSON mode, and an 8192-token limit to avoid empty content and length-limited DeepSeek V4 responses.
- Improved DeepSeek response compatibility for missing `shot_id`, unknown fields, schema validation, and malformed or empty output; mismatched shot IDs remain rejected.
- Classified DeepSeek API errors, AI prompt schema-validation errors, and local prompt-processing errors separately in the UI.
- Preserved an existing Prompt Pack when an AI generation attempt fails.
- Prevented `reasoning_content` from entering the UI, Prompt Packs, history, JSON exports, or logs.
- Prevented platform adapters from rewriting canonical prompt content during export.

## v0.3.2

Release date: 2026-08-06

### Added

- Added a unified single-button mode switcher.
- Added a stable light desktop design system and reusable UI components.
- Added desktop-width layout coverage for the Standard Creator and Professional JSON workspaces.

### Improved

- Reworked the AI Creator home page around creative input, production settings, and recent projects.
- Unified the top navigation and visual language across AI Creator, Standard Creator, and Professional JSON modes.
- Updated Standard Creator to use a desktop two-input-card layout.
- Updated Professional JSON to use separate file, verification-control, status, and issue-list areas.
- Removed duplicate in-page API status and API settings controls.
- Improved minimum-window usability, spacing, button hierarchy, and content width.

### Compatibility

- Existing generation, analysis, verification, history, import, and export protocols are unchanged.
- API Key storage and usage are unchanged.
- Creator history JSON, `GenerationResult`, `StoryboardDraft`, and verification-report formats are unchanged.

## v0.3.1 Windows Release acceptance and publishing safety

- Added repeatable Windows Release acceptance for Setup, Portable ZIP, SHA256SUMS, manifest metadata, UTF-8 creator history, and API-key leakage checks.
- Added a GitHub Actions release gate plus pull-request and manual dry-run paths; only `v*` tag pushes can enter the write-permission publish job.
- Preserved Creator history format, API-key storage, install location, and Creator functionality.

## v0.3.0 Public Beta / release candidate

- Added AI Creator generation, strict DeepSeek JSON handling, StoryboardBuilder normalization, validation, and one bounded AI repair.
- Added AI Creator desktop mode, result copying/JSON export, local history, and frozen Creator smoke coverage.
- Creator history keeps up to 50 records and migrates compatible records from the former history directory.

### Known limitations

- AI Creator requires DeepSeek API access.
- Full StoryBible / ScenePlan reference validation, shot editing, partial regeneration, and cloud sync are not available.

## v0.2.0 Public Beta

This is a public beta / release candidate. A GitHub Release has not been
published yet.

### Included

- Creator mode for adapting natural-language scripts and director plans.
- Professional JSON mode for direct `facts.json` and `director_output.json`
  verification.
- Deterministic local rules for locked-fact consistency checks.
- Optional DeepSeek semantic auditing, using the user's own API key.
- Windows installer and portable ZIP distribution builds.
- DeepSeek API-key storage through Windows Credential Manager.
- JSON verification-report export.
- CI packaging with SHA256 checksums and a release manifest.

### Known limitations

- Semantic auditing is experimental and requires human review.
- The score measures consistency with locked production facts, not artistic
  quality.
- The verifier does not inspect generated visual frames, rendered video,
  lip-sync, or actual camera movement.
- Windows artifacts still require the manual acceptance checks recorded in the
  release checklist before publication.
