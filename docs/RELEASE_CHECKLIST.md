# v0.2.0 Public Beta Release Checklist

This checklist is for the public beta / release candidate. Do not mark it as a
published GitHub Release until the release is actually created.

## Automatically completed by CI

- [ ] `pytest`
- [ ] CLI examples
- [ ] PyInstaller build
- [ ] EXE smoke test
- [ ] Portable ZIP
- [ ] Inno Setup installer
- [ ] sensitive-information scan
- [ ] SHA256 checksums
- [ ] release manifest
- [ ] artifact upload

## Manual acceptance

- [ ] Portable build launches.
- [ ] Installer build installs successfully.
- [ ] Start-menu shortcut works.
- [ ] Desktop shortcut works.
- [ ] Installed application launches.
- [ ] API Key can be added, changed, and deleted.
- [ ] Creator Mode makes a real API call with a user-provided DeepSeek API Key.
- [ ] Semantic Audit makes a real API call with a user-provided DeepSeek API Key.
- [ ] An invalid API Key produces a clear, safe error.
- [ ] Offline and timeout behavior is clear and recoverable.
- [ ] TXT, MD, DOCX, and JSON import works.
- [ ] The layout is usable at 100%, 125%, 150%, and 200% Windows DPI scaling.
- [ ] Uninstall behavior and residual files are reviewed.
- [ ] The artifacts are checked on a clean Windows computer.
- [ ] SmartScreen / unknown-publisher prompts are reviewed and documented.
