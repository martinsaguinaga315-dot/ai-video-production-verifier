from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from llm_audit import semantic_audit
from models import DirectorOutput, ProjectFacts, VerificationReport
from rules import verify as verify_hard_rules


def load_json(path: Path) -> Any:
    """Read and decode one UTF-8 JSON file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_report(
    hard_report: VerificationReport,
    semantic_issues: list,
) -> VerificationReport:
    """Combine hard-rule and semantic issues into one final report."""
    issues = list(hard_report.issues) + list(semantic_issues)

    errors = sum(
        issue.severity == "error"
        for issue in issues
    )
    warnings = sum(
        issue.severity == "warning"
        for issue in issues
    )

    return VerificationReport(
        passed=errors == 0,
        score=max(
            0,
            100 - errors * 10 - warnings * 3,
        ),
        errors=errors,
        warnings=warnings,
        issues=issues,
    )


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify an AI video production plan against "
            "locked project facts."
        )
    )

    parser.add_argument(
        "facts",
        type=Path,
        help="Path to facts.json",
    )
    parser.add_argument(
        "director_output",
        type=Path,
        help="Path to director_output.json",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help=(
            "Run DeepSeek semantic auditing in addition "
            "to deterministic hard rules."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the JSON verification report.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON instead of indented JSON.",
    )

    return parser


def main() -> int:
    load_dotenv()

    parser = create_parser()
    args = parser.parse_args()

    try:
        facts_data = load_json(args.facts)
        output_data = load_json(args.director_output)

        facts = ProjectFacts.model_validate(
            facts_data
        )
        director_output = DirectorOutput.model_validate(
            output_data
        )
    except FileNotFoundError as exc:
        print(
            f"Input file not found: {exc.filename}",
            file=sys.stderr,
        )
        return 2
    except json.JSONDecodeError as exc:
        print(
            (
                "Invalid JSON: "
                f"{exc.msg} at line {exc.lineno}, "
                f"column {exc.colno}"
            ),
            file=sys.stderr,
        )
        return 2
    except ValidationError as exc:
        print(
            "Input schema validation failed:",
            file=sys.stderr,
        )
        print(
            exc,
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(
            f"Unable to read input: {exc}",
            file=sys.stderr,
        )
        return 2

    try:
        hard_report = verify_hard_rules(
            facts,
            director_output,
        )
    except Exception as exc:
        print(
            f"Hard-rule verification failed: {exc}",
            file=sys.stderr,
        )
        return 3

    semantic_issues = []

    if args.semantic:
        try:
            semantic_issues = semantic_audit(
                facts,
                director_output,
                hard_report.issues,
            )
        except Exception as exc:
            print(
                f"Semantic audit failed: {exc}",
                file=sys.stderr,
            )
            return 4

    report = build_report(
        hard_report,
        semantic_issues,
    )

    indent = None if args.compact else 2
    report_text = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        indent=indent,
    )

    if args.output:
        try:
            args.output.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            args.output.write_text(
                report_text + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(
                f"Unable to write report: {exc}",
                file=sys.stderr,
            )
            return 5
    else:
        print(report_text)

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())