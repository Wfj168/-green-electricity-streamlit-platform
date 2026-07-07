from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "results"
FIGURE_DIR = ROOT / "assets" / "figures"
MODEL_DIR = ROOT / "src" / "model"


REQUIRED_FILES = [
    DATA_DIR / "planning_summary_v17_3_1.csv",
    DATA_DIR / "operation_summary_v17_3_1.csv",
    DATA_DIR / "carbon_management_decomposition_v17_3_9.csv",
    DATA_DIR / "operation" / "R4" / "data" / "dispatch_results.csv",
    DATA_DIR / "operation" / "R4" / "data" / "metrics_results.csv",
    MODEL_DIR / "model_core_v17_3_1_county.py",
    MODEL_DIR / "scenarios_v17_3_1_county.py",
    MODEL_DIR / "data_profiles_v17_3_3_county_region.py",
    MODEL_DIR / "carbon_management_v17_3_9.py",
]


DISPATCH_COLUMNS = [
    "hour",
    "day_name",
    "electric_load",
    "heat_load",
    "P_grid_buy",
    "P_PV",
    "P_WT",
    "P_BAT_ch",
    "P_BAT_dis",
    "SOC_BAT",
    "co2_emission",
]


SUMMARY_COLUMNS = [
    "Scenario",
    "Private total annual cost [million CNY/year]",
    "Annual CO2 emissions [tCO2/year]",
    "Renewable local absorption rate [%]",
    "Renewable curtailment rate [%]",
]


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def run_static_checks() -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    for path in REQUIRED_FILES:
        rows.append(
            {
                "检查项": path.name,
                "状态": "通过" if path.exists() else "缺失",
                "说明": str(path.relative_to(ROOT)) if path.exists() else f"未找到 {path}",
            }
        )

    figures = sorted(FIGURE_DIR.glob("*.png")) if FIGURE_DIR.exists() else []
    rows.append(
        {
            "检查项": "论文结果图 PNG",
            "状态": "通过" if len(figures) >= 19 else "需处理",
            "说明": f"当前检测到 {len(figures)} 张 PNG，预期不少于 19 张。",
        }
    )

    try:
        planning = _read_csv(DATA_DIR / "planning_summary_v17_3_1.csv")
        missing = [c for c in SUMMARY_COLUMNS if c not in planning.columns]
        rows.append(
            {
                "检查项": "规划汇总字段",
                "状态": "通过" if not missing else "需处理",
                "说明": "关键字段齐全。" if not missing else "缺少：" + "、".join(missing),
            }
        )
        rows.append(
            {
                "检查项": "S0-S8规划场景",
                "状态": "通过" if set(f"S{i}" for i in range(9)).issubset(set(planning["Scenario"])) else "需处理",
                "说明": f"当前包含 {planning['Scenario'].nunique()} 个规划场景。",
            }
        )
    except Exception as exc:
        rows.append({"检查项": "规划汇总读取", "状态": "报错", "说明": str(exc)})

    try:
        dispatch = _read_csv(DATA_DIR / "operation" / "R4" / "data" / "dispatch_results.csv")
        missing = [c for c in DISPATCH_COLUMNS if c not in dispatch.columns]
        rows.append(
            {
                "检查项": "R4调度字段",
                "状态": "通过" if not missing else "需处理",
                "说明": "调度图关键字段齐全。" if not missing else "缺少：" + "、".join(missing),
            }
        )
        rows.append(
            {
                "检查项": "R4调度时段",
                "状态": "通过" if len(dispatch) > 0 else "需处理",
                "说明": f"当前包含 {len(dispatch)} 条调度记录。",
            }
        )
    except Exception as exc:
        rows.append({"检查项": "R4调度读取", "状态": "报错", "说明": str(exc)})

    return pd.DataFrame(rows)


def old_platform_note() -> str:
    return (
        "已按 StoreMore 手册功能和你之前平台的页面结构进行融合。"
        "由于 https://storemore-clone-v5.streamlit.app/ 当前在本环境无法直接读取源码，"
        "本次融合以功能逻辑为准：侧边栏导航、模型设置、结果图、指标分析、案例对比、绿电直连。"
        "如果后续提供旧平台源码，可以进一步做逐项界面迁移。"
    )
