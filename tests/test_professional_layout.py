from pathlib import Path


SOURCE = Path("creator_desktop/main_window.py").read_text(encoding="utf-8")


def test_professional_mode_uses_four_light_cards_and_keeps_actions() -> None:
    start = SOURCE.index("def _build_professional_light_layout")
    section = SOURCE[start:SOURCE.index("def _light_path_row", start)]
    for token in (
        "professional_files_card", "professional_controls_card", "professional_status_card",
        "professional_results_card", "facts.json", "director_output.json", "开始核验",
        "加载正常示例", "加载错误示例", "导出 JSON 报告",
    ):
        assert token in section
    assert "API设置" not in section
    assert "textvariable=self.api_status" not in section


def test_topbar_remains_the_single_api_status_location() -> None:
    assert SOURCE.count("StatusText(tools, textvariable=self.creator_api_status)") == 1
