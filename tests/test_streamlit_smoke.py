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


def test_integrated_planning_configuration_runs_end_to_end() -> None:
    app = AppTest.from_file("app.py", default_timeout=60).run()
    app.selectbox[0].set_value("V17综合能源规划")
    app.run(timeout=60)
    app.radio[0].set_value("参数配置与运行")
    app.run(timeout=60)
    assert not app.exception

    run_button = next(button for button in app.button if button.label == "开始综合能源规划")
    run_button.click()
    app.run(timeout=60)

    assert not app.exception
    execution = app.session_state["integrated_result"]
    assert execution.success is True
    assert execution.summary["scenario_key"] == "S4"

    navigation = app.radio[0]
    assert navigation.options == [
        "平台概览",
        "项目与任务",
        "参数配置与运行",
        "多能流结果",
        "综合规划指标",
        "绿电直连规划",
        "结果导出",
        "工程架构",
    ]
    for page in navigation.options:
        navigation.set_value(page)
        app.run(timeout=60)
        assert not app.exception, f"综合规划页面加载失败：{page}"
