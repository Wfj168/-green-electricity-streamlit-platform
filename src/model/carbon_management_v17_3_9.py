from __future__ import annotations

from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


SCENARIO_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
MODULE_LABELS = {
    "S0": "基准系统",
    "S1": "低碳约束",
    "S2": "储能协同",
    "S3": "柔性负荷",
    "S4": "源荷储协同",
    "S5": "低空韧性",
    "S6": "园区净零",
    "S7": "绿电直连",
    "S8": "P2X深度脱碳",
}


def _metric(path: Path, name: str, default: float = 0.0) -> float:
    try:
        df = pd.read_csv(path)
        row = df[df["Metric"] == name]
        return float(row["Value"].iloc[0]) if not row.empty else default
    except Exception:
        return default


def _scenario_params(scenarios: Mapping[str, dict], key: str) -> dict:
    common = scenarios.get("COMMON", {}) if isinstance(scenarios, dict) else {}
    scenario = scenarios.get(key, {}) if isinstance(scenarios, dict) else {}
    out = dict(common)
    out.update(scenario)
    return out


def enrich_carbon_management_v17_3_9(
    result_root: Path,
    planning_summary: pd.DataFrame,
    planning_scenarios: Mapping[str, dict],
) -> pd.DataFrame:
    """Add paper-oriented carbon-management diagnostics and write auxiliary CSVs.

    The added indicators are accounting/diagnostic metrics for paper analysis.
    They do not change the optimization results already solved in model_core.
    """
    rows = []
    for _, row in planning_summary.iterrows():
        s = str(row["Scenario"])
        if s not in SCENARIO_ORDER:
            continue
        params = _scenario_params(planning_scenarios, s)
        grid_ef = float(params.get("grid_emission_factor", 0.55))
        gas_ef = float(params.get("gas_emission_factor", 0.20))
        dispatch_path = result_root / "planning" / s / "data" / "dispatch_results.csv"
        metrics_path = result_root / "planning" / s / "data" / "metrics_results.csv"
        dispatch = pd.read_csv(dispatch_path)
        w = dispatch["dt"].to_numpy(float) * dispatch["day_weight"].to_numpy(float)
        grid_em = float(np.sum(dispatch["P_grid_buy"].to_numpy(float) * grid_ef * w))
        chp_em = float(np.sum(dispatch["G_CHP"].to_numpy(float) * gas_ef * w))
        gb_em = float(np.sum(dispatch["G_GB"].to_numpy(float) * gas_ef * w))
        actual_em = float(row.get("Annual CO2 emissions [tCO2/year]", grid_em + chp_em + gb_em))
        p2x_avoided = _metric(metrics_path, "Endogenous P2X CO2 avoidance", _metric(metrics_path, "CO2 reduction potential from P2X", 0.0))
        p2x_elec = _metric(metrics_path, "Endogenous P2X electricity consumption", 0.0)
        h2_heat = _metric(metrics_path, "Endogenous H2 heat supply", 0.0)
        h2_prod = _metric(metrics_path, "Endogenous green hydrogen production", 0.0)
        elz_cap = _metric(metrics_path, "Electrolyzer capacity", 0.0)
        elz_flh = _metric(metrics_path, "Electrolyzer full-load hours", 0.0)
        green_direct_target = float(row.get("Green-direct target electricity [MWh/year]", 0.0) or 0.0)
        green_direct_avoided = green_direct_target * grid_ef
        accounting_credit = p2x_avoided + green_direct_avoided
        accounting_net = max(0.0, actual_em - green_direct_avoided)
        park_load = float(row.get("Annual industrial-park electric load [MWh/year]", 0.0) or 0.0)
        park_heat = float(row.get("Annual industrial-park process heat load [MWh/year]", 0.0) or 0.0)
        park_green = float(row.get("Industrial-park local renewable coverage [%]", 0.0) or 0.0)
        park_heat_sub = 100.0 * h2_heat / park_heat if park_heat > 1e-9 else 0.0
        allowance = params.get("carbon_allowance_tco2_per_year", np.nan)
        try:
            allowance = float(allowance) if allowance is not None else np.nan
        except Exception:
            allowance = np.nan
        allowance_gap = actual_em - allowance if np.isfinite(allowance) else np.nan
        residual_after_mgmt = max(0.0, actual_em - green_direct_avoided)
        rows.append({
            "Scenario": s,
            "Scenario name": row.get("Name", s),
            "Module label": MODULE_LABELS.get(s, s),
            "Grid import emissions [tCO2/year]": grid_em,
            "CHP gas emissions [tCO2/year]": chp_em,
            "Gas boiler emissions [tCO2/year]": gb_em,
            "Operational CO2 emissions [tCO2/year]": actual_em,
            "Green-direct avoided emissions proxy [tCO2/year]": green_direct_avoided,
            "Endogenous P2X avoided emissions [tCO2/year]": p2x_avoided,
            "Carbon-management credit proxy [tCO2/year]": accounting_credit,
            "Accounting net CO2 after green-direct credit [tCO2/year]": accounting_net,
            "Carbon allowance [tCO2/year]": allowance,
            "Carbon allowance gap [tCO2/year]": allowance_gap,
            "Industrial-park local renewable coverage [%]": park_green,
            "Industrial-park heat substituted by H2 [%]": park_heat_sub,
            "Endogenous P2X electricity [MWh/year]": p2x_elec,
            "Endogenous H2 heat supply [MWh/year]": h2_heat,
            "Endogenous green hydrogen production [tH2/year]": h2_prod,
            "Electrolyzer capacity [MW]": elz_cap,
            "Electrolyzer full-load hours [h/year]": elz_flh,
            "Residual CO2 after carbon-management credits [tCO2/year]": residual_after_mgmt,
        })
    carbon_df = pd.DataFrame(rows)
    if carbon_df.empty:
        return planning_summary
    baseline = float(carbon_df.loc[carbon_df["Scenario"] == "S0", "Operational CO2 emissions [tCO2/year]"].iloc[0])
    carbon_df["CO2 reduction vs S0 [tCO2/year]"] = baseline - carbon_df["Operational CO2 emissions [tCO2/year]"]
    carbon_df["CO2 reduction vs S0 [%]"] = 100.0 * carbon_df["CO2 reduction vs S0 [tCO2/year]"] / max(baseline, 1e-9)
    # Net-zero proximity is reported on an operational-emissions basis to avoid
    # overstating market-credit effects. Green-direct and P2X credits are shown
    # separately in the decomposition figures.
    carbon_df["Net-zero proximity [%]"] = 100.0 * (1.0 - carbon_df["Operational CO2 emissions [tCO2/year]"] / max(baseline, 1e-9))
    carbon_df["Net-zero proximity [%]"] = carbon_df["Net-zero proximity [%]"].clip(lower=0.0, upper=100.0)

    # Marginal abatement cost and pathway diagnostics.
    summary_idx = planning_summary.set_index("Scenario")
    path_rows = []
    prev_s = None
    prev_em = prev_cost = None
    for s in SCENARIO_ORDER:
        if s not in summary_idx.index:
            continue
        em = float(summary_idx.loc[s, "Annual CO2 emissions [tCO2/year]"])
        cost = float(summary_idx.loc[s, "Social total annual cost [million CNY/year]"])
        if prev_s is None:
            inc_red = 0.0
            inc_cost = 0.0
            inc_mac = np.nan
        else:
            inc_red = prev_em - em
            inc_cost = cost - prev_cost
            inc_mac = inc_cost * 1e6 / inc_red if abs(inc_red) > 1e-9 else np.nan
        total_red = baseline - em
        total_cost = cost - float(summary_idx.loc["S0", "Social total annual cost [million CNY/year]"])
        avg_mac = total_cost * 1e6 / total_red if abs(total_red) > 1e-9 else np.nan
        path_rows.append({
            "Scenario": s,
            "Module label": MODULE_LABELS.get(s, s),
            "Annual CO2 emissions [tCO2/year]": em,
            "Social total annual cost [million CNY/year]": cost,
            "Incremental CO2 reduction [tCO2/year]": inc_red,
            "Incremental cost change [million CNY/year]": inc_cost,
            "Incremental MAC [CNY/tCO2]": inc_mac,
            "Total CO2 reduction vs S0 [tCO2/year]": total_red,
            "Total cost change vs S0 [million CNY/year]": total_cost,
            "Average abatement cost vs S0 [CNY/tCO2]": avg_mac,
        })
        prev_s, prev_em, prev_cost = s, em, cost
    pathway_df = pd.DataFrame(path_rows)

    # Technology contribution proxy.  This is used for explanation figures, not for
    # causal proof; adjacent scenario differences are interpreted as module effects.
    contrib_rows = []
    for _, r in pathway_df.iterrows():
        if r["Scenario"] == "S0":
            continue
        contrib_rows.append({
            "Module": r["Module label"],
            "Scenario": r["Scenario"],
            "Incremental CO2 reduction [tCO2/year]": r["Incremental CO2 reduction [tCO2/year]"],
            "Incremental cost change [million CNY/year]": r["Incremental cost change [million CNY/year]"],
            "Incremental MAC [CNY/tCO2]": r["Incremental MAC [CNY/tCO2]"],
        })
    contrib_df = pd.DataFrame(contrib_rows)

    # Write CSV files.
    carbon_df.to_csv(result_root / "carbon_management_decomposition_v17_3_9.csv", index=False, encoding="utf-8-sig")
    pathway_df.to_csv(result_root / "carbon_management_pathway_v17_3_9.csv", index=False, encoding="utf-8-sig")
    contrib_df.to_csv(result_root / "carbon_reduction_contribution_v17_3_9.csv", index=False, encoding="utf-8-sig")

    # Merge key fields into planning_summary.
    add_cols = carbon_df[[
        "Scenario",
        "Grid import emissions [tCO2/year]",
        "CHP gas emissions [tCO2/year]",
        "Gas boiler emissions [tCO2/year]",
        "Green-direct avoided emissions proxy [tCO2/year]",
        "Endogenous P2X avoided emissions [tCO2/year]",
        "Accounting net CO2 after green-direct credit [tCO2/year]",
        "CO2 reduction vs S0 [tCO2/year]",
        "CO2 reduction vs S0 [%]",
        "Net-zero proximity [%]",
        "Industrial-park heat substituted by H2 [%]",
        "Endogenous P2X electricity [MWh/year]",
        "Endogenous H2 heat supply [MWh/year]",
        "Endogenous green hydrogen production [tH2/year]",
        "Electrolyzer capacity [MW]",
        "Electrolyzer full-load hours [h/year]",
    ]]
    out = planning_summary.merge(add_cols, on="Scenario", how="left")
    mac_cols = pathway_df[[
        "Scenario",
        "Incremental CO2 reduction [tCO2/year]",
        "Incremental cost change [million CNY/year]",
        "Incremental MAC [CNY/tCO2]",
        "Average abatement cost vs S0 [CNY/tCO2]",
    ]]
    out = out.merge(mac_cols, on="Scenario", how="left")
    return out
