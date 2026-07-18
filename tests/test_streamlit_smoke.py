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


def test_project_page_degrades_safely_for_invalid_api_url(monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_API_URL", "not-a-valid-url")
    app = AppTest.from_file("app.py", default_timeout=30).run()
    navigation = app.radio[0]
    navigation.set_value("项目与任务")
    app.run(timeout=30)
    assert not app.exception
    assert any("后台地址配置无效" in value for value in app.markdown.values)
