from __future__ import annotations


class CreatorImportError(Exception):
    """Safe base error: never include full user text, keys, or LLM responses."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.details = details or []


class FileReadError(CreatorImportError):
    pass


class UnsupportedFileError(FileReadError):
    pass


class EmptyFileError(FileReadError):
    pass


class FileTooLargeError(FileReadError):
    pass


class LLMRequestError(CreatorImportError):
    def __init__(self, message: str, code: str = "llm_failed") -> None:
        super().__init__(message)
        self.code = code


class JsonStructureError(CreatorImportError):
    pass


class ExtractionValidationError(CreatorImportError):
    pass
