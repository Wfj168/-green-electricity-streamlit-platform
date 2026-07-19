from __future__ import annotations

import pandas as pd

from src.storemore_engine import (
    StoreMoreInputs,
    default_capex_table,
    default_fuel_table,
    default_generator_table,
    default_storage_table,
    run_storemore_simulation,
)


def run_static_checks() -> pd.DataFrame:
    checks: list[dict[str, str]] = []
    required_columns = {
        "generator": ["Unit Name", "Installed Capacity [MW]", "Max Investment [MW]"],
        "storage": ["Unit Name", "Installed Capacity [MWh]", "Efficiency [-]"],
        "fuel": ["Fuel", "Cost", "Unit"],
        "capex": ["Technology", "Annual investment cost [M CNY/year]"],
    }
    tables = {
        "generator": default_generator_table(),
        "storage": default_storage_table(),
        "fuel": default_fuel_table(),
        "capex": default_capex_table(),
    }
    for name, columns in required_columns.items():
        missing = [col for col in columns if col not in tables[name].columns]
        checks.append(
            {
                "检查项": f"{name} 参数表",
                "状态": "通过" if not missing else "需处理",
                "说明": "字段完整" if not missing else "缺少字段：" + "、".join(missing),
            }
        )

    inputs = StoreMoreInputs(
        scenario_name="diagnostic",
        total_demand=1_000_000.0,
        service_life=25,
        import_price=90.0,
        export_price=70.0,
        import_export_capacity=500.0,
        rps_constraint=True,
        min_res_share=35.0,
        co2_constraint=False,
        max_co2=100_000.0,
        ceep_constraint=False,
        max_ceep=20.0,
        optimize_capacity=True,
        restrict_investments=False,
        rolling_days=1,
        country_code="CN",
    )
    result = run_storemore_simulation(
        inputs,
        default_generator_table(),
        default_storage_table(),
        default_fuel_table(),
        default_capex_table(),
    )
    checks.append(
        {
            "检查项": "默认场景实时优化",
            "状态": "通过" if result.get("success") else "报错",
            "说明": str(result.get("message")),
        }
    )
    return pd.DataFrame(checks)
