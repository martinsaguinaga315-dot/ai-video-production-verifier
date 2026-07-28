"""Shared orchestration for CLI and desktop verification clients.

This module deliberately reuses the stable rules, models and semantic-audit
modules.  It only owns input handling, orchestration and safe error boundaries.
"""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from pydantic import ValidationError

from llm_audit import semantic_audit
from models import DirectorOutput, ProjectFacts, VerificationReport
from rules import verify as verify_hard_rules


StatusCallback = Callable[[str], None]
_API_KEY_ENV_LOCK = threading.Lock()


class VerificationServiceError(Exception):
    """Base class whose string form is safe to show to an end user."""


class InputFileNotFoundError(VerificationServiceError):
    pass


class InputJsonError(VerificationServiceError):
    pass


class InputSchemaError(VerificationServiceError):
    pass


class HardVerificationError(VerificationServiceError):
    pass


class SemanticVerificationError(VerificationServiceError):
    """A semantic failure with a safe, UI-displayable category."""

    def __init__(self, message: str, code: str = "semantic_failed") -> None:
        super().__init__(message)
        self.code = code


class ReportWriteError(VerificationServiceError):
    pass


def _notify(callback: StatusCallback | None, message: str) -> None:
    if callback:
        callback(message)


def load_json(path: Path) -> Any:
    """Read one UTF-8 JSON document with a safe public error message."""
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as exc:
        raise InputFileNotFoundError(f"文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise InputJsonError(
            f"JSON格式错误（第{exc.lineno}行，第{exc.colno}列）。"
        ) from exc
    except OSError as exc:
        raise InputFileNotFoundError(f"无法读取文件：{path}") from exc


def _validate_inputs(
    facts_data: Any,
    director_output_data: Any,
) -> tuple[ProjectFacts, DirectorOutput]:
    try:
        return (
            ProjectFacts.model_validate(facts_data),
            DirectorOutput.model_validate(director_output_data),
        )
    except ValidationError as exc:
        # ValidationError can contain long user-provided values.  The GUI and
        # CLI only need to know that the schema is invalid.
        raise InputSchemaError("输入文件结构不符合核验器要求。") from exc


def _semantic_error_code(error: Exception) -> str:
    """Classify provider failures without retaining provider response content."""
    status_code = getattr(error, "status_code", None)
    if status_code == 401:
        return "api_key_invalid"
    if status_code == 429:
        return "rate_limited"
    if status_code in (402, 403):
        return "insufficient_permission"
    if isinstance(status_code, int) and status_code >= 500:
        return "service_unavailable"

    name = type(error).__name__.lower()
    if "authentication" in name:
        return "api_key_invalid"
    if "ratelimit" in name:
        return "rate_limited"
    if "permission" in name:
        return "insufficient_permission"
    if "timeout" in name or isinstance(error, TimeoutError):
        return "timeout"
    if "connection" in name or "connect" in name:
        return "connection_failed"
    if "internalserver" in name:
        return "service_unavailable"
    return "semantic_failed"


@contextmanager
def _temporary_api_key(api_key: str | None) -> Iterator[None]:
    """Expose a supplied key only for the semantic call, then restore env."""
    if api_key is None:
        yield
        return

    cleaned_key = api_key.strip()
    if not cleaned_key:
        raise SemanticVerificationError(
            "未配置DeepSeek API Key。",
            "api_key_missing",
        )

    with _API_KEY_ENV_LOCK:
        previous = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = cleaned_key
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = previous


def build_report(
    hard_report: VerificationReport,
    semantic_issues: list,
) -> VerificationReport:
    """Combine issue sources and calculate the public report contract."""
    issues = list(hard_report.issues) + list(semantic_issues)
    errors = sum(issue.severity == "error" for issue in issues)
    warnings = sum(issue.severity == "warning" for issue in issues)
    return VerificationReport(
        passed=errors == 0,
        score=max(0, 100 - errors * 10 - warnings * 3),
        errors=errors,
        warnings=warnings,
        issues=issues,
    )


def run_verification(
    facts_path: str | Path,
    director_output_path: str | Path,
    *,
    semantic: bool = False,
    api_key: str | None = None,
    status_callback: StatusCallback | None = None,
) -> VerificationReport:
    """Run the stable verification pipeline without changing stable rules."""
    facts_file = Path(facts_path)
    output_file = Path(director_output_path)

    _notify(status_callback, "正在读取文件")
    facts_data = load_json(facts_file)
    output_data = load_json(output_file)

    _notify(status_callback, "正在检查结构")
    facts, director_output = _validate_inputs(facts_data, output_data)

    return run_verification_models(
        facts,
        director_output,
        semantic=semantic,
        api_key=api_key,
        status_callback=status_callback,
    )


def run_verification_models(
    facts: ProjectFacts,
    director_output: DirectorOutput,
    *,
    semantic: bool = False,
    api_key: str | None = None,
    status_callback: StatusCallback | None = None,
) -> VerificationReport:
    """Verify already-confirmed in-memory models for creator mode.

    This is the same stable pipeline used by ``run_verification`` after file
    loading; it avoids writing intermediate creator drafts to disk.
    """
    _notify(status_callback, "正在执行本地硬规则")
    try:
        hard_report = verify_hard_rules(facts, director_output)
    except Exception as exc:
        raise HardVerificationError("本地硬规则核验失败。") from exc

    semantic_issues: list = []
    if semantic:
        _notify(status_callback, "正在执行语义审计")
        try:
            with _temporary_api_key(api_key):
                semantic_issues = semantic_audit(
                    facts,
                    director_output,
                    hard_report.issues,
                )
        except SemanticVerificationError:
            raise
        except Exception as exc:
            # Provider exceptions may include headers or response bodies.
            raise SemanticVerificationError(
                "DeepSeek语义审计失败。",
                _semantic_error_code(exc),
            ) from exc

    _notify(status_callback, "正在生成结果")
    return build_report(hard_report, semantic_issues)


def write_report(
    report: VerificationReport,
    output_path: str | Path,
    *,
    compact: bool = False,
) -> None:
    """Persist a report while keeping write failures out of clients."""
    path = Path(output_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                report.model_dump(mode="json"),
                ensure_ascii=False,
                indent=None if compact else 2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ReportWriteError(f"无法写入报告：{path}") from exc
