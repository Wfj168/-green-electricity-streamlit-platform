from __future__ import annotations

import subprocess
import sys

from streamlit.testing.v1 import AppTest


def test_app_import_survives_legacy_core_module_cache() -> None:
    code = """
import src.core

for name in (
    "PHASE1_PARAMETER_REGISTRY",
    "formal_readiness_gaps",
    "phase1_parameter_value",
):
    delattr(src.core, name)

import app
assert app.PHASE1_PARAMETER_REGISTRY
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_all_streamlit_pages_render_without_uncaught_exceptions() -> None:
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    assert len(app.radio) == 1

    navigation = app.radio[0]
    assert navigation.options == ["平台概览", "参数配置与运行", "运行分析", "场景与决策"]
    for page in navigation.options:
        navigation.set_value(page)
        app.run(timeout=30)
        assert not app.exception, f"页面加载失败：{page}"


def test_project_center_is_hidden_for_invalid_api_url(monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_API_URL", "not-a-valid-url")
    app = AppTest.from_file("app.py", default_timeout=30).run()
    navigation = app.radio[0]
    assert not app.exception
    assert "项目中心" not in navigation.options
    assert any("项目中心已隐藏" in value for value in app.caption.values)


def test_integrated_planning_configuration_runs_end_to_end() -> None:
    app = AppTest.from_file("app.py", default_timeout=60).run()
    app.selectbox[0].set_value("V17农业零碳园区规划")
    app.run(timeout=60)
    app.radio[0].set_value("参数配置与运行")
    app.run(timeout=60)
    assert not app.exception

    next(checkbox for checkbox in app.checkbox if checkbox.label == "显示原V17县域综合能源兼容配置").check()
    app.run(timeout=60)

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
        "参数配置与运行",
        "运行分析",
        "场景与决策",
    ]
    for page in navigation.options:
        navigation.set_value(page)
        app.run(timeout=60)
        assert not app.exception, f"综合规划页面加载失败：{page}"

    app.radio[0].set_value("场景与决策")
    app.run(timeout=60)
    next(checkbox for checkbox in app.checkbox if checkbox.label == "显示原V17县域多场景兼容功能").check()
    app.run(timeout=60)
    compare_button = next(button for button in app.button if button.label == "运行真实场景对比")
    compare_button.click()
    app.run(timeout=60)
    assert not app.exception
    comparison = app.session_state["scenario_comparison_result"]
    assert comparison.success is True
    assert comparison.table["场景"].tolist() == [f"S{index}" for index in range(9)]


def test_data_forecast_and_intraday_page_runs_end_to_end() -> None:
    app = AppTest.from_file("app.py", default_timeout=60).run()
    app.radio[0].set_value("参数配置与运行")
    app.run(timeout=60)

    next(checkbox for checkbox in app.checkbox if checkbox.label == "显示15分钟数据校验与预测工具").check()
    app.run(timeout=60)

    next(button for button in app.button if button.label == "加载14天示例数据并检查").click()
    app.run(timeout=60)
    assert app.session_state["timeseries_validation"].valid is True

    next(button for button in app.button if button.label == "评估基准并生成日前96点预测").click()
    app.run(timeout=60)
    forecast = app.session_state["day_ahead_forecast"]
    assert forecast.horizon_points == 96

    next(button for button in app.button if button.label == "生成日内滚动请求").click()
    app.run(timeout=60)
    plan = app.session_state["intraday_plan"]
    assert plan.forecast_version == forecast.version_id
    assert plan.inherited_state == {"battery_soc_fraction": 0.5, "thermal_soc_fraction": 0.5}
