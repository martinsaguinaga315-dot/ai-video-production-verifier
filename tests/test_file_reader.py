from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from creator_import.extraction_errors import EmptyFileError, FileTooLargeError, UnsupportedFileError
from creator_import.file_reader import read_text_file


def test_reads_utf8_txt(tmp_path: Path) -> None:
    path = tmp_path / "script.txt"
    path.write_text("中文剧本", encoding="utf-8")
    assert read_text_file(path).text == "中文剧本"


def test_reads_utf8_bom_and_gb18030(tmp_path: Path) -> None:
    bom = tmp_path / "bom.txt"
    bom.write_bytes("带BOM".encode("utf-8-sig"))
    gb = tmp_path / "gb18030.txt"
    gb.write_bytes("中文编码".encode("gb18030"))
    assert read_text_file(bom).text == "带BOM"
    assert read_text_file(gb).text == "中文编码"


def test_reads_markdown_docx_and_chinese_space_path(tmp_path: Path) -> None:
    markdown = tmp_path / "中文 空格.md"
    markdown.write_text("# 标题", encoding="utf-8")
    docx_path = tmp_path / "方案 文档.docx"
    document = Document()
    document.add_paragraph("DOCX内容")
    document.save(docx_path)
    assert read_text_file(markdown).file_type == "md"
    assert read_text_file(docx_path).text == "DOCX内容"


def test_file_errors_are_safe(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    unknown = tmp_path / "source.pdf"
    unknown.write_bytes(b"data")
    large = tmp_path / "large.txt"
    large.write_text("12345", encoding="utf-8")
    with pytest.raises(EmptyFileError):
        read_text_file(empty)
    with pytest.raises(UnsupportedFileError):
        read_text_file(unknown)
    with pytest.raises(FileTooLargeError):
        read_text_file(large, max_bytes=4)
