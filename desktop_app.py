"""Source entry point for the CustomTkinter desktop application."""
from __future__ import annotations

import sys

from creator_desktop.app import run
from creator_desktop.frozen_creator_smoke import run_frozen_creator_smoke


def main(argv: list[str] | None = None) -> int:
    if (sys.argv[1:] if argv is None else argv) == ["--smoke-creator-ui"]:
        return run_frozen_creator_smoke()
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
