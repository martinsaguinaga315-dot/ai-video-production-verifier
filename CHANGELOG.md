# Changelog

All notable changes to this project are documented here.

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
