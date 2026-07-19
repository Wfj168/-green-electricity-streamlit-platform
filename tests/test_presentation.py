from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from src.application import ModelExecutionRequest, UnifiedModelService
from src.presentation import localize_v17_table


def test_v17_cost_and_metric_tables_are_localized_to_cny() -> None:
    cost = pd.DataFrame(
        {
            "Cost item": ["Social total annual cost"],
            "Value": [25_000_000.0],
            "Unit": ["CNY/year"],
        }
    )
    localized = localize_v17_table("cost", cost)

    assert localized.columns.tolist() == ["成本项目", "数值", "单位"]
    assert localized.iloc[0].to_dict() == {
        "成本项目": "社会年度总成本",
        "数值": 2500.0,
        "单位": "万元/年",
    }


def test_v17_export_contains_chinese_result_tables() -> None:
    result = UnifiedModelService().run(
        ModelExecutionRequest(
            "integrated_planning",
            {"scenario_key": "S4", "n_steps_per_hour": 1, "seed": 42},
        )
    )

    assert result.success is True, result.message
    with ZipFile(BytesIO(result.artifact_bytes or b"")) as archive:
        assert {
            "结果表/容量配置.csv",
            "结果表/多能调度.csv",
            "结果表/成本明细.csv",
            "结果表/碳排放.csv",
            "结果表/综合指标.csv",
            "结果表/运行诊断.csv",
        }.issubset(archive.namelist())


def test_user_facing_source_contains_no_euro_currency_labels() -> None:
    root = Path(__file__).resolve().parents[1]
    source_files = [root / "app.py", *root.joinpath("src").rglob("*.py")]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in source_files)

    assert "EUR" not in combined
    assert "€" not in combined
