from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_all_streamlit_pages_render_without_uncaught_exceptions() -> None:
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    assert len(app.radio) == 1

    navigation = app.radio[0]
    assert len(navigation.options) == 8
    for page in navigation.options:
        navigation.set_value(page)
        app.run(timeout=30)
        assert not app.exception, f"页面加载失败：{page}"
