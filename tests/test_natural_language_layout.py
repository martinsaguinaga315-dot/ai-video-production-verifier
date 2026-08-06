from pathlib import Path


SOURCE = Path("creator_desktop/natural_language_view.py").read_text(encoding="utf-8")


def test_creator_header_and_description_use_the_shared_page_structure() -> None:
    assert 'PageTitle(self.content, text="普通创作")' in SOURCE
    assert 'text="通过脚本要求和导演方案，快速生成结构化分析结果。"' in SOURCE
    assert 'self.content.grid(row=0, column=0, padx=PAGE_GUTTER, pady=(12, 18), sticky="new")' in SOURCE


def test_creator_input_panels_expand_before_footer() -> None:
    assert 'self.input_area.grid_columnconfigure((0, 1), weight=1, uniform="creator_inputs")' in SOURCE
    assert 'self.script_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")' in SOURCE
    assert 'self.director_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")' in SOURCE
    assert 'self.footer.grid(row=3, column=0, pady=(14, 0), sticky="ew")' in SOURCE


def test_creator_workflow_controls_and_text_remain_available() -> None:
    for text in ("加载示例", "自动分析", "_on_analyze", "普通创作", "导入文件", "清空", "api_status"):
        assert text in SOURCE
    assert 'text="API设置"' not in SOURCE
    assert "textvariable=api_status" not in SOURCE


def test_creator_input_explains_required_shot_timing() -> None:
    for text in ("镜头编号", "总时长", "每个镜头起止时间"):
        assert text in SOURCE
