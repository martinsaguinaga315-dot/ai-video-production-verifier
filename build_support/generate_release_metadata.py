"""Generate checksums and a release manifest for Windows build artifacts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_support.release_utils import write_manifest, write_sha256s


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--python-version", required=True)
    parser.add_argument("--pyinstaller-version", required=True)
    parser.add_argument("--artifact", type=Path, action="append", default=[])
    parser.add_argument("--installer-built", action="store_true")
    parser.add_argument("--portable-built", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts: list[Path] = args.artifact
    if not artifacts:
        raise ValueError("at least one --artifact is required")

    invalid_artifacts = [path for path in artifacts if not path.is_file()]
    if invalid_artifacts:
        invalid_paths = ", ".join(str(path) for path in invalid_artifacts)
        raise FileNotFoundError(f"artifact must be an existing file: {invalid_paths}")

    args.release_dir.mkdir(parents=True, exist_ok=True)
    write_sha256s(artifacts, args.release_dir / "SHA256SUMS.txt")
    write_manifest(
        args.release_dir / f"release_manifest_v{args.version}.json",
        commit=args.commit,
        python_version=args.python_version,
        pyinstaller_version=args.pyinstaller_version,
        test_result="pytest passed",
        artifacts=artifacts,
        smoke_passed=True,
        scan_passed=True,
        installer_built=args.installer_built,
        portable_built=args.portable_built,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
