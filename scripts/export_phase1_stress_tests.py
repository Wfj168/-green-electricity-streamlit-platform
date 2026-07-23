from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.application.agri_stress_test_service import (  # noqa: E402
    AgriReferenceCapacities,
    AgriStressTestService,
)
from src.model.agri_park_profiles import generate_agri_park_profiles  # noqa: E402


def main() -> None:
    comparison = pd.read_csv(
        ROOT / "data" / "demo" / "phase1_strategy_comparison.csv",
        encoding="utf-8-sig",
    )
    zero = comparison.loc[comparison["策略"].eq("零碳源网荷储协同方案")].iloc[0]
    capacities = AgriReferenceCapacities(
        pv_capacity_mw=float(zero["本地光伏/兆瓦"]),
        green_direct_capacity_mw=float(zero["绿电直连/兆瓦"]),
        battery_power_mw=float(zero["储能功率/兆瓦"]),
        battery_energy_mwh=float(zero["储能容量/兆瓦时"]),
    )
    result = AgriStressTestService().evaluate(
        generate_agri_park_profiles(2025, 60),
        capacities,
        planning_interval_hours=3,
    )
    output = ROOT / "data" / "demo" / "phase1_stress_test_results.csv"
    result.table.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"已导出六类压力测试：{output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
