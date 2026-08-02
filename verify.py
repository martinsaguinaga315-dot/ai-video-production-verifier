from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from verification_service import (
    HardVerificationError,
    InputFileNotFoundError,
    InputJsonError,
    InputSchemaError,
    ReportWriteError,
    SemanticVerificationError,
    run_verification,
    write_report,
)


def configure_utf8_stdio() -> None:
    """Keep CLI JSON and diagnostics readable on legacy Windows code pages."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


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
    configure_utf8_stdio()
    load_dotenv()

    parser = create_parser()
    args = parser.parse_args()

    try:
        report = run_verification(
            args.facts,
            args.director_output,
            semantic=args.semantic,
        )
    except (InputFileNotFoundError, InputJsonError, InputSchemaError) as exc:
        print(exc, file=sys.stderr)
        return 2
    except HardVerificationError as exc:
        print(exc, file=sys.stderr)
        return 3
    except SemanticVerificationError as exc:
        print(exc, file=sys.stderr)
        return 4

    if args.output:
        try:
            write_report(report, args.output, compact=args.compact)
        except ReportWriteError as exc:
            print(exc, file=sys.stderr)
            return 5
    else:
        import json

        print(json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=None if args.compact else 2,
        ))

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
