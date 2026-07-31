from pathlib import Path


SOURCE = Path("creator_desktop/natural_language_view.py").read_text(encoding="utf-8")


def test_creator_header_and_privacy_notice_use_separate_rows() -> None:
    title = 'text="普通创作者模式"'
    privacy = 'text="自然语言结构化和语义审计会将相关文本发送到用户自行配置的DeepSeek接口。软件不内置API Key，不提供遥测上传。"'

    assert f"{title}, font=ctk.CTkFont(size=22, weight=\"bold\")).grid(row=0" in SOURCE
    assert f"{privacy}, wraplength=900, justify=\"left\").grid(row=1" in SOURCE
    assert "pady=(45, 8)" not in SOURCE


def test_creator_input_panels_expand_before_footer() -> None:
    assert "self.grid_rowconfigure(2, weight=1)" in SOURCE
    assert "panel.grid(row=2, column=column" in SOURCE
    assert "footer.grid(row=3, column=0" in SOURCE


def test_creator_workflow_controls_and_text_remain_available() -> None:
    for text in ("加载示例", "自动分析", "_on_analyze", "普通创作者模式"):
        assert text in SOURCE
