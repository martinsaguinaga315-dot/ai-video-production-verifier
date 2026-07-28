"""Safe text extraction for creator-mode source files."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from creator_import.extraction_errors import (
    EmptyFileError,
    FileReadError,
    FileTooLargeError,
    UnsupportedFileError,
)


SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx", ".json"}
DEFAULT_MAX_BYTES = 2_000_000


@dataclass(frozen=True)
class ReadText:
    text: str
    file_type: str
    char_count: int


def _decode_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise FileReadError("无法识别文件编码，请保存为UTF-8、GB18030或GBK后重试。")


def _read_docx(path: Path) -> str:
    try:
        from docx import Document

        document = Document(path)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except FileReadError:
        raise
    except Exception as exc:
        raise FileReadError("无法读取DOCX文件，请确认文件未损坏。") from exc


def read_text_file(path: str | Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> ReadText:
    """Read an approved text format without logging its content."""
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError("暂不支持此文件格式，请使用TXT、Markdown、DOCX或JSON。")
    try:
        size = source.stat().st_size
    except FileNotFoundError as exc:
        raise FileReadError("找不到导入文件，请重新选择。") from exc
    except OSError as exc:
        raise FileReadError("无法读取导入文件。") from exc
    if size > max_bytes:
        raise FileTooLargeError("文件过大，请缩短内容后重新导入。")

    text = _read_docx(source) if suffix == ".docx" else _decode_text(source)
    if not text.strip():
        raise EmptyFileError("文件内容为空，请检查后重新导入。")
    return ReadText(text=text, file_type=suffix.lstrip("."), char_count=len(text))
