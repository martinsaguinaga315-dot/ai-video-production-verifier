# Manual Acceptance Record — v0.2.0 Public Beta

This document records observed manual acceptance results for the current public
beta / release candidate. It is not evidence that a GitHub Release has been
published.

## Passed

- Release artifact files are present.
- Portable ZIP SHA256 was verified on a real Windows computer.
- Setup EXE SHA256 was verified on a real Windows computer.
- Portable build launches.
- The portable build does not open a console window.
- The application has a Chinese title and icon.
- Examples load.
- Mode switching works.
- The normal Professional JSON example scores 100 with 0 errors.
- The Professional JSON unknown-character example reports `UNKNOWN_CHARACTER`.
- JSON report export works.

## Revalidate after this fix

- UI-DPI-001: verify the creator-mode layout at 150% Windows DPI scaling after
  the header and privacy notice are separated into distinct grid rows.

## Not completed

- Installer acceptance.
- API-key management and real API / semantic-audit calls.
- TXT, MD, DOCX, and JSON file import.
- Uninstall behavior and residual-file review.
- Acceptance on a clean Windows computer.
