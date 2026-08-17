"""Verification facade over the existing stable verification service."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import VerificationFacadeError


def verify_project(
    facts: Any,
    director_output: Any,
    *,
    semantic: bool = False,
    api_key: str | None = None,
    status_callback: Callable[[str], None] | None = None,
    runner: Callable[..., Any] | None = None,
) -> Any:
    """Verify already-confirmed in-memory models.

    The runner is resolved lazily and is injectable. Web v0.1 should keep
    ``semantic=False`` until provider credentials are fully server-scoped.
    """
    if runner is None:
        from verification_service import run_verification_models

        runner = run_verification_models

    try:
        return runner(
            facts,
            director_output,
            semantic=semantic,
            api_key=api_key,
            status_callback=status_callback,
        )
    except VerificationFacadeError:
        raise
    except Exception as exc:
        raise VerificationFacadeError(
            "ImagiFrame Core verification could not complete."
        ) from exc
