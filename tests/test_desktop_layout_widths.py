from pathlib import Path


NATURAL = Path("creator_desktop/natural_language_view.py").read_text(encoding="utf-8")
MAIN = Path("creator_desktop/main_window.py").read_text(encoding="utf-8")


def test_standard_mode_content_and_cards_expand_across_the_desktop_width() -> None:
    assert 'padx=PAGE_GUTTER, pady=(12, 18), sticky="new"' in NATURAL
    assert 'grid_columnconfigure((0, 1), weight=1, uniform="creator_inputs")' in NATURAL
    assert 'sticky="nsew"' in NATURAL
    assert 'padx=(0, 10)' in NATURAL and 'padx=(10, 0)' in NATURAL
    assert "height=400" in NATURAL and "height=250" in NATURAL


def test_standard_mode_keeps_all_card_actions_and_aligned_footer() -> None:
    for token in ("导入文件", "清空", "加载示例", "StatusText(self.footer", "PrimaryButton(self.footer"):
        assert token in NATURAL


def test_professional_mode_content_and_file_row_expand_without_narrow_widths() -> None:
    start = MAIN.index("def _build_professional_light_layout")
    section = MAIN[start:MAIN.index("def _light_path_row", start)]
    assert 'padx=PAGE_GUTTER, pady=(12, 18), sticky="new"' in section
    assert 'content.grid_columnconfigure(0, weight=1)' in section
    assert 'self.professional_results_card.grid(row=5, column=0, pady=(14, 0), sticky="nsew")' in section
    assert "width=320" not in section


def test_professional_file_controls_and_results_remain_visible_components() -> None:
    section = MAIN[MAIN.index("def _light_path_row"):]
    for token in ("textvariable=variable", "选择文件", "清除", "width=90", "width=64"):
        assert token in section
    for token in ("仅本地硬规则", "硬规则 + DeepSeek语义审计", "加载正常示例", "加载错误示例", "开始核验", "self.results", "self.export_button"):
        assert token in MAIN
