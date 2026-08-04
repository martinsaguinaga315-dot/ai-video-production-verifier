"""Source-development wrapper; the release gate invokes the frozen EXE instead."""
from __future__ import annotations

from creator_desktop.frozen_creator_smoke import run_frozen_creator_smoke

if __name__ == "__main__":
    raise SystemExit(run_frozen_creator_smoke())
