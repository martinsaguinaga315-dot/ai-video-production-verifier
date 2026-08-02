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

## Release-blocking manual acceptance template

Complete the following in order on the final `v0.2.0 Public Beta` candidate.
For every row, record the observed result and the location of any evidence.
“Block release” means the item must pass before an authorized GitHub Release
may be published.

| ID | Priority / environment | Steps | Expected result | Actual result / evidence link | Block release | On failure, preserve |
| --- | --- | --- | --- | --- | --- | --- |
| MA-P0-001 | P0 — Windows test PC | Run `AI-Video-Production-Verifier-Setup-v0.2.0.exe`; finish the installer. | Installation completes without an unhandled error. | _Fill in_ | Yes | Installer screenshot and install log. |
| MA-P0-002 | P0 — installed application | Launch from the Start-menu shortcut. | The application opens with its icon and no console window. | _Fill in_ | Yes | Screenshot and Windows Event Viewer entry, if present. |
| MA-P0-003 | P0 — installed application | Launch from the desktop shortcut. | The same installed application opens successfully. | _Fill in_ | Yes | Screenshot and shortcut properties. |
| MA-P0-004 | P0 — installed application | Uninstall from Windows Settings; inspect Start menu, desktop, and the install directory. | Uninstall completes and leaves no user-visible application residue except explicitly documented user data. | _Fill in_ | Yes | Screenshot plus remaining-path list. |
| MA-P1-001 | P1 — Creator Mode with a valid user-owned DeepSeek key | Enter the key, save it, and run one real semantic audit. | A real request completes; result is visible and the key is not shown in logs or UI. | _Fill in_ | Yes | Screenshot with key redacted and relevant log excerpt. |
| MA-P1-002 | P1 — Creator Mode with an invalid key | Replace the key with an invalid value and run the same action. | A clear, user-safe authentication error appears; no crash or key leak. | _Fill in_ | Yes | Screenshot and relevant log excerpt. |
| MA-P1-003 | P1 — offline network | Disconnect the network and start a semantic audit. | A clear recoverable offline error appears. | _Fill in_ | Yes | Screenshot and relevant log excerpt. |
| MA-P1-004 | P1 — induced network timeout | Use a controlled timeout condition and start a semantic audit. | A clear recoverable timeout error appears. | _Fill in_ | Yes | Screenshot and relevant log excerpt. |
| MA-P1-005 | P1 — semantic-audit output | Review a successful semantic-audit response against the input. | Result is plausible, marked experimental, and manually reviewed; no accuracy guarantee is claimed. | _Fill in_ | Yes | Input, redacted response, and reviewer decision. |
| MA-P2-001 | P2 — import feature | Import representative UTF-8 TXT, Markdown, DOCX, and JSON files, including Chinese text. | Each format imports correctly or shows a clear format-specific error. | _Fill in_ | No | Sample file and screenshot/log. |
| MA-P3-001 | P3 — Windows display scaling | At 100%, 125%, 150%, and 200% DPI, inspect Creator Mode and Professional Mode. | Text, controls, Chinese font rendering, privacy notice, and dialogs remain usable with no clipping. | _Fill in for each scale_ | Yes | Screenshot per DPI scale. |
| MA-P4-001 | P4 — clean Windows PC | On a machine with no Python, Git, or development environment, install and launch the application; run the portable ZIP too. | Both distributables work without development tools. | _Fill in_ | Yes | System details, screenshots, and logs. |

## Final authorization record

Only after every blocking row passes, record the approver, date, tested commit,
artifact SHA256 values, and explicit authorization to merge to `main`, create
the tag, and publish the GitHub Release. This remains a Public Beta / Release
Candidate until that authorization is given.
