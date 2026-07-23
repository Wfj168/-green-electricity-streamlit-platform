from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.application.agri_strategy_service import AgriStrategyService  # noqa: E402
from src.model.agri_park_profiles import generate_agri_park_profiles  # noqa: E402


def main() -> None:
    profiles = generate_agri_park_profiles(2025, 60)
    result = AgriStrategyService().compare(profiles)
    output = ROOT / "data" / "demo" / "phase1_strategy_comparison.csv"
    result.comparison.to_csv(output, index=False, encoding="utf-8-sig")
    result.green_direct.annual_flows.to_csv(
        ROOT / "data" / "demo" / "phase1_green_direct_annual_flows.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame([result.zero_carbon.summary]).to_csv(
        ROOT / "data" / "demo" / "phase1_zero_carbon_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    dispatch_columns = [
        "timestamp",
        "pv_to_load_mw",
        "direct_to_load_mw",
        "battery_discharge_total_mw",
        "grid_to_load_mw",
        "optimized_total_load_mw",
        "pv_to_battery_mw",
        "direct_to_battery_mw",
        "battery_soc_pv_mwh",
        "battery_soc_direct_mwh",
        "pv_curtailment_mw",
        "direct_curtailment_mw",
    ]
    result.zero_carbon.dispatch[dispatch_columns].to_csv(
        ROOT / "data" / "demo" / "phase1_zero_carbon_dispatch.csv.gz",
        index=False,
        encoding="utf-8-sig",
        compression="gzip",
    )
    print(f"已导出三策略对比：{output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
