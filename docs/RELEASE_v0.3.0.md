# v0.3.0 Release Notes

Release type: Public Beta / release candidate.

AI Creator adds `idea/style/goal → DeepSeek → StoryboardDraft → validation → at most one AI repair`, desktop result copying/export, and local history.

Windows assets: `AI-Video-Production-Verifier-Setup-v0.3.0.exe` and `AI-Video-Production-Verifier-Portable-v0.3.0.zip`.

The checked baseline is 219 automated tests. API keys stay in Windows Credential Manager and are not saved to exports or Creator history. History is kept at `%LOCALAPPDATA%\AIVideoProductionVerifier\creator_history`, with compatibility migration from the former directory.

Known limits: DeepSeek is required for Creator; full StoryBible/ScenePlan validation, shot editing, partial regeneration, and cloud sync are not yet included.
