---
name: ai-video-production-verifier
description: Validate structured AI video storyboards and production plans before image or video generation. Detect timeline, dialogue, character, prop, event, continuity, identity, and action-feasibility problems.
---

# AI Video Production Verifier

Validate an AI video production plan against locked project facts before generation begins.

The verifier combines deterministic hard rules with an optional DeepSeek semantic audit.

## Use this skill when

Use this skill when the user needs to:

- check an AI storyboard before production
- validate a multi-shot AI short film
- detect dialogue or shot-attribution errors
- detect unauthorized characters or props
- check timeline gaps, overlaps, and duration mismatches
- check required and forbidden events
- check character identity and state continuity
- check prop position and physical-state continuity
- check event order
- check whether too many actions are assigned to a short shot
- produce a machine-readable verification report

## Do not use this skill when

Do not use this skill to:

- generate an actual image or video
- inspect rendered video frames
- perform face recognition
- rewrite the user's story without permission
- replace locked facts with inferred content
- treat stylistic changes as identity changes without explicit evidence
- automatically modify production files without user approval

## Required input

The skill requires two UTF-8 JSON files.

### `facts.json`

Contains locked production facts, including:

- total duration
- shot count
- expected shot boundaries
- exact dialogue
- required events
- forbidden events
- locked characters
- locked props
- global restrictions

### `director_output.json`

Contains the proposed production plan, including:

- character cards
- prop cards
- locations
- shots
- opening and ending states
- action paths
- first-frame prompts
- video prompts
- generation segments
- dialogue

Both inputs must satisfy the Pydantic models defined in `models.py`.

## Verification pipeline

Run the following stages in order:

1. Load and validate both JSON files.
2. Execute deterministic hard rules through `rules.verify`.
3. When semantic auditing is enabled, pass the hard-rule issues into `llm_audit.semantic_audit`.
4. Normalize semantic rule families.
5. Remove issues already owned by hard rules.
6. Merge issues that describe the same root cause.
7. Calculate the final score.
8. Return a structured verification report.

Do not skip hard-rule verification before semantic auditing.

## Deterministic checks

The hard-rule layer checks items such as:

- `SHOT_COUNT`
- `DUPLICATE_ID`
- `DURATION_MISMATCH`
- `TIME_GAP`
- `TIME_OVERLAP`
- `TOTAL_DURATION`
- `UNKNOWN_CHARACTER`
- `UNKNOWN_PROP`
- `MISSING_SHOT`
- `LOCKED_TIME`
- `MISSING_EVENT`
- `EVENT_WRONG_SHOT`
- `FORBIDDEN_EVENT`
- `DIALOGUE_EXACT`
- `SPEECH_TOO_LONG`
- `SPEECH_TIGHT`
- `GLOBAL_FORBIDDEN`
- `PROP_STATE`
- `MISSING_CHARACTER`
- `APPEARANCE_MISSING`
- `APPEARANCE_CHANGED`
- `INITIAL_STATE_MISSING`
- `COSTUME_MISSING`
- `COSTUME_CHANGED`
- `PROP_OWNER_MISMATCH`
- `PROP_OWNER_UNVERIFIED`
- `SEGMENT_MISSING`
- `SEGMENT_INCOMPLETE`
- `SEGMENT_NAME_DUPLICATE`
- `SEGMENT_DURATION_INVALID`
- `SEGMENT_DURATION_TOTAL`
- `FIRST_FRAME_MOTION`
- `SEGMENT_FIRST_FRAME_MOTION`
- `GEOMETRY_CONFLICT`
- `RAILING_CONFLICT`
- `SPEED_CONFLICT`
- `AUDIO_TAIL`

## Semantic checks

The optional semantic layer currently supports these principal rule families:

- `SEMANTIC_STATE_CONTINUITY`
- `SEMANTIC_PROP_CONTINUITY`
- `SEMANTIC_IDENTITY_CONTINUITY`
- `SEMANTIC_ACTION_FEASIBILITY`
- `SEMANTIC_EVENT_ORDER`

Only report a semantic issue when explicit evidence confirms that the violation exists.

Do not report speculative concerns as errors.

Do not return multiple issues for the same root cause.

## Environment setup

Install dependencies:

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS or Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Semantic auditing requires environment variables:

```env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

Copy `.env.example` to `.env` and insert the API key.

Never commit `.env`.

## Run deterministic verification

```bash
python verify.py examples/clean/facts.json examples/clean/director_output.json
```

Save the report:

```bash
python verify.py \
  examples/clean/facts.json \
  examples/clean/director_output.json \
  --output verification_report.json
```

## Run semantic verification

```bash
python verify.py \
  examples/clean/facts.json \
  examples/clean/director_output.json \
  --semantic
```

## Example error case

```bash
python verify.py \
  examples/unknown_character_error/facts.json \
  examples/unknown_character_error/director_output.json
```

Expected principal issue:

```text
UNKNOWN_CHARACTER
```

## CLI arguments

```text
verify.py [-h] [--semantic] [--output OUTPUT] [--compact]
          facts director_output
```

Arguments:

- `facts`: path to `facts.json`
- `director_output`: path to `director_output.json`
- `--semantic`: enable DeepSeek semantic auditing
- `--output`: write the report to a JSON file
- `--compact`: output compact JSON

## Exit codes

- `0`: verification completed and no errors were found
- `1`: verification completed and one or more errors were found
- `2`: input, JSON, or schema validation failure
- `3`: deterministic verification failure
- `4`: semantic audit failure
- `5`: report-writing failure

Warnings do not cause exit code `1` unless an error is also present.

## Output contract

The verifier returns:

```json
{
  "passed": true,
  "score": 100,
  "errors": 0,
  "warnings": 0,
  "issues": []
}
```

Each issue contains:

```json
{
  "rule_id": "UNKNOWN_CHARACTER",
  "severity": "error",
  "title": "出现事实层未定义人物",
  "message": "导演输出擅自增加人物。",
  "path": "characters[1].character_id",
  "evidence": "characters[1].character_id",
  "suggestion": "删除该人物或先在facts中正式定义。"
}
```

## Scoring

Current scoring:

- each error deducts 10 points
- each warning deducts 3 points
- minimum score is 0
- `passed` is true only when error count is 0

The score is an operational quality indicator, not a measure of artistic quality.

## Rules for agents

When invoking this skill:

1. Preserve the user's locked facts.
2. Never silently rewrite dialogue.
3. Never invent characters, props, or events.
4. Run deterministic checks before semantic checks.
5. Pass hard-rule issues into the semantic audit.
6. Do not duplicate an issue already reported by a hard rule.
7. Merge issues with the same subject, boundary, and root cause.
8. Point every issue to the field containing the evidence.
9. Separate confirmed violations from suggestions.
10. State clearly when the semantic API was unavailable.
11. Do not claim that an unexecuted semantic audit passed.
12. Do not modify input files unless the user explicitly approves a repair.

## Current limitations

Version `0.1.0` validates structured production plans only.

It does not yet:

- inspect generated images
- inspect generated video
- verify visual identity from pixels
- detect lip-sync errors
- verify actual camera movement
- automatically repair production plans
- provide a web interface
- provide an MCP server
- guarantee complete interpretation of complex mixed-light descriptions

Scene-light continuity support is limited and should be treated as experimental.

## Recommended agent response

After verification, report:

- whether verification passed
- final score
- error and warning counts
- rules triggered
- affected shot or field paths
- concise repair suggestions
- whether semantic auditing was executed
