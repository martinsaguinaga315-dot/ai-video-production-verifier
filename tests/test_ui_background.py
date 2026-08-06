from creator_desktop.ui_background import AmbientBackground


def test_background_is_a_canvas_without_image_dependencies():
    assert AmbientBackground.__bases__[0].__name__ == "Canvas"
