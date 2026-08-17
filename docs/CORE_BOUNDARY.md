# ImagiFrame Core Boundary v1

Status: W2 baseline  
Scope: `imagiframe_core` public facade  
Base repository: `ai-video-production-verifier`

## Purpose

`imagiframe_core` is the stable application-facing entry point for ImagiFrame
business logic.

Web, Desktop, CLI, and future integrations should migrate toward:

```python
from imagiframe_core import create_storyboard
```

instead of importing deeply from implementation modules.

The facade does **not** replace `story_generation`. It protects consumers from
future internal refactors.

## Dependency direction

```text
Web --------Desktop -----+--> imagiframe_core --> story_generation / verification_service
CLI --------/
```

Never reverse this dependency.

`story_generation` must not import Web or Desktop code.

## Responsibilities allowed inside `imagiframe_core`

- stable request contracts;
- thin orchestration boundaries;
- Core-safe error classification;
- storyboard generation entry points;
- deterministic Prompt Pack entry points;
- prompt-platform adaptation entry points;
- in-memory verification entry points.

## Responsibilities forbidden inside `imagiframe_core`

- CustomTkinter widgets;
- Windows Credential Manager / keyring;
- `%LOCALAPPDATA%` history;
- HTTP request/response objects;
- FastAPI routes;
- Next.js concerns;
- PostgreSQL sessions;
- user accounts;
- subscriptions, Credits, payments;
- object-storage persistence;
- model-provider billing;
- direct UI notifications.

Those belong to Desktop or Web application layers.

## Persistence rule

Core computes artifacts.

Desktop decides how local artifacts are stored.

Web decides how cloud artifacts are stored.

The facade must not silently persist Storyboards, Prompt Packs, Assets, or
verification reports.

## Credential rule

Core functions accept explicit credential injection where legacy internals need
it.

Web server credentials must remain server-scoped. Browser clients must never
receive DeepSeek, Kling, Jimeng, Veo, storage, or payment-provider secrets.

The existing semantic verification path currently has legacy environment-based
credential compatibility. Web v0.1 should keep semantic verification disabled
until that credential path is fully server-safe.

## Prompt Adapter vs Generation Provider

These are different layers.

```text
Canonical Prompt Pack
        |
        v
PromptPlatformAdapter
        |
        v
Kling/Jimeng/Veo formatted prompt
```

This does not call a remote generation API.

Future remote execution belongs to a separate Generation Provider / Generation
Gateway layer.

## Public ID rule

Domain IDs produced inside the current generation pipeline are not cloud
database primary keys.

Web must generate its own server-owned IDs such as:

- `user_id`
- `project_id`
- `request_id`
- `job_id`
- `asset_id`

Do not use legacy fixed values such as `brief-user-idea` as multi-user database
identity.

## W2 non-goals

W2 intentionally does not:

- move existing `story_generation` modules;
- rename existing public classes;
- change Storyboard behavior;
- change Prompt Pack behavior;
- change Desktop UI;
- change Video Analysis;
- call real Kling/Jimeng/Veo APIs;
- add FastAPI;
- add PostgreSQL;
- add Credits or payments.

## Exit criteria

W2 is ready for W3 when:

1. application code can import `imagiframe_core`;
2. facade unit tests run offline;
3. facade calls are injectable in tests;
4. no Desktop dependency is required by the facade;
5. existing Core behavior remains untouched.

After this checkpoint, W3-A may create the private `imagiframe-web` skeleton
with Next.js + FastAPI and a `/health` vertical slice.
