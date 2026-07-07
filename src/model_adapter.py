from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "src" / "model"
DATA_DIR = ROOT / "data" / "results"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from data_profiles_v17_3_3_county_region import generate_county_region_profiles_v17_3_3
from model_core_v17_3_1_county import solve_integrated_energy_system_v17_3_1
from scenarios_v17_3_1_county import (
    get_operation_scenarios_v17_3_1,
    get_planning_scenarios_v17_3_1,
)


def _load_fixed_capacities() -> dict[str, float]:
    path = DATA_DIR / "planning" / "S4" / "data" / "capacity_results.csv"
    if not path.exists():
        return {}
    capacity = pd.read_csv(path, encoding="utf-8-sig")
    if not {"Technology", "Capacity"}.issubset(capacity.columns):
        return {}
    return {
        str(row["Technology"]): float(row["Capacity"])
        for _, row in capacity.iterrows()
        if pd.notna(row["Capacity"])
    }


def build_scenario(base_key: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    key = base_key.upper().strip()
    overrides = overrides or {}
    if key.startswith("S"):
        scenarios = get_planning_scenarios_v17_3_1()
    elif key.startswith("R"):
        scenarios = get_operation_scenarios_v17_3_1(_load_fixed_capacities())
    else:
        raise ValueError(f"不支持的场景编号：{base_key}")
    if key not in scenarios:
        raise KeyError(f"未找到场景：{base_key}")
    scenario = dict(scenarios[key])
    for name, value in overrides.items():
        if value is not None:
            scenario[name] = value
    return scenario


def run_quick_trial(
    scenario_key: str,
    overrides: dict[str, Any] | None = None,
    n_steps_per_hour: int = 1,
    seed: int = 42,
) -> dict[str, Any]:
    try:
        scenario = build_scenario(scenario_key, overrides)
        scenario.setdefault("milp_time_limit", 20.0)
        scenario.setdefault("mip_rel_gap", 0.02)
        scenario["solver_display"] = False
        profiles = generate_county_region_profiles_v17_3_3(
            n_steps_per_hour=n_steps_per_hour,
            seed=seed,
        )
        result = solve_integrated_energy_system_v17_3_1(profiles, scenario)
        return {
            "success": bool(result.get("success", False)),
            "message": result.get("message", "快速试算完成。"),
            "result": result,
            "profiles": profiles,
            "scenario": scenario,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"快速试算失败，已回退到正式结果展示：{exc}",
            "result": None,
            "profiles": None,
            "scenario": None,
        }
