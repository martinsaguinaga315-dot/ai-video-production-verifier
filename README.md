# AI Video Production Verifier

A pre-production validation tool for structured AI video storyboards and shot plans.

It checks locked facts against a proposed director output before image or video generation begins.

## What it checks

Deterministic rules cover:

- shot count and locked shot boundaries
- duration mismatches
- timeline gaps and overlaps
- exact dialogue and shot attribution
- required, forbidden, and misplaced events
- unauthorized characters and props
- character appearance, costume, and initial-state locks
- prop ownership and forbidden prop states
- generation-segment completeness and duration totals
- first-frame motion warnings
- basic geometry and action conflicts

Optional DeepSeek semantic auditing adds:

- `SEMANTIC_STATE_CONTINUITY`
- `SEMANTIC_PROP_CONTINUITY`
- `SEMANTIC_IDENTITY_CONTINUITY`
- `SEMANTIC_ACTION_FEASIBILITY`
- `SEMANTIC_EVENT_ORDER`

## Current status

Version: `0.2.0-dev`

Current checked baseline:

- 2 versioned CLI example cases
- 14 non-network pytest checks for the shared service, CLI, credentials, and controller
- no live semantic API calls in automated tests

The semantic layer is experimental. The deterministic layer is the primary stable interface.

## Requirements

- Python 3.11+
- Windows, macOS, or Linux
- DeepSeek API key only when using `--semantic`

## Installation

```bash
git clone https://github.com/martinsaguinaga315-dot/ai-video-production-verifier.git
cd ai-video-production-verifier
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS or Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick start

Run the clean deterministic example:

```bash
python verify.py examples/clean/facts.json examples/clean/director_output.json
```

Expected result:

```json
{
  "passed": true,
  "score": 100,
  "errors": 0,
  "warnings": 0,
  "issues": []
}
```

Run the unknown-character example:

```bash
python verify.py examples/unknown_character_error/facts.json examples/unknown_character_error/director_output.json
```

Expected principal issue:

```text
UNKNOWN_CHARACTER
```

The process exits with code `1` when verification completes and one or more errors are found.

## Save a report

```bash
python verify.py \
  examples/clean/facts.json \
  examples/clean/director_output.json \
  --output verification_report.json
```

Use compact JSON:

```bash
python verify.py \
  examples/clean/facts.json \
  examples/clean/director_output.json \
  --compact
```

## Semantic auditing

Copy the environment template:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS or Linux:

```bash
cp .env.example .env
```

Set:

```env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

Then run:

```bash
python verify.py \
  examples/clean/facts.json \
  examples/clean/director_output.json \
  --semantic
```

Never commit `.env`.

## Windows desktop app (JSON professional mode)

The source desktop app lets you select existing `facts.json` and
`director_output.json` files, run local hard-rule verification or optional
DeepSeek semantic auditing, inspect issues, and export the JSON report.

```powershell
pip install -r requirements-desktop.txt
python desktop_app.py
```

The desktop app stores the DeepSeek API key in Windows Credential Manager; it
does not put the key in a project JSON file, report, or ordinary settings file.
Natural-language conversion and packaging are not part of this release stage.

## CLI

```text
verify.py [-h] [--semantic] [--output OUTPUT] [--compact]
          facts director_output
```

Exit codes:

| Code | Meaning |
|---:|---|
| 0 | Verification completed with no errors |
| 1 | Verification completed and errors were found |
| 2 | Input, JSON, or schema validation failed |
| 3 | Deterministic verification failed |
| 4 | Semantic auditing failed |
| 5 | Report output failed |

## Input files

### `facts.json`

Defines locked production facts:

- total duration
- shot count
- expected shots and time boundaries
- exact dialogue
- required and forbidden events
- locked characters
- locked props
- global restrictions

### `director_output.json`

Defines the proposed production plan:

- character and prop cards
- locations
- shots
- opening and ending states
- actions
- dialogue
- first-frame prompts
- video prompts
- generation segments

Both inputs are validated with the Pydantic models in `models.py`.

## Output

```json
{
  "passed": false,
  "score": 90,
  "errors": 1,
  "warnings": 0,
  "issues": [
    {
      "rule_id": "UNKNOWN_CHARACTER",
      "severity": "error",
      "title": "出现事实层未定义人物",
      "message": "导演输出擅自增加人物。",
      "path": "characters[1].character_id",
      "evidence": "characters[1].character_id",
      "suggestion": "删除该人物或先在facts中正式定义。"
    }
  ]
}
```

Scoring:

- each error deducts 10 points
- each warning deducts 3 points
- minimum score is 0
- `passed` is true only when there are no errors

The score measures production-plan compliance, not artistic quality.

## Repository layout

```text
.
├── SKILL.md
├── README.md
├── verify.py
├── models.py
├── rules.py
├── llm_audit.py
├── requirements.txt
├── .env.example
├── .gitignore
└── examples/
    ├── clean/
    │   ├── facts.json
    │   ├── director_output.json
    │   └── verification_report.json
    └── unknown_character_error/
        ├── facts.json
        ├── director_output.json
        └── verification_report.json
```

## Design principles

- locked facts are authoritative
- deterministic rules run before semantic auditing
- semantic results must not duplicate hard-rule findings
- one root cause should produce one final issue
- every issue must point to the field containing its evidence
- speculative concerns must not be returned as confirmed errors
- input files are never modified automatically

## Limitations

Version `0.1.0` does not yet:

- inspect generated images or video
- perform visual identity verification
- detect lip-sync errors
- validate actual camera motion
- automatically repair production plans
- provide a web interface
- provide an MCP server
- fully interpret complex mixed-light transitions

Scene-light continuity is currently experimental.

## Skill usage

See [`SKILL.md`](SKILL.md) for agent-specific invocation rules, workflow requirements, and output behavior.

## Roadmap

Planned directions:

- structured JSON Patch repair suggestions
- replayable semantic responses
- improved model-output recovery and retry
- REST and MCP interfaces
- visual frame continuity checks
- rendered-video quality assurance

## License

Licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).
