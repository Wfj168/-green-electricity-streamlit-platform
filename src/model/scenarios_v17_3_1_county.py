from __future__ import annotations

from copy import deepcopy


COMMON_PARAMS = {
    # Basic economics
    "discount_rate": 0.05,
    "life_years": 20,
    "fixed_om_rate": 0.02,
    "enable_chp": True,

    # Grid interface: local-consumption oriented, with limited export.
    "enable_grid_export": True,
    "grid_import_capacity": 120.0,
    "grid_export_capacity": 5.0,
    "max_annual_export_share_of_renewables": 0.10,
    "grid_export_wheeling_charge": 8.0,
    "grid_export_capacity_charge": 6000.0,
    "strict_grid_exchange_exclusivity": False,

    # Prevent export-led renewable overbuild.
    "max_renewable_energy_to_service_demand_ratio": 1.15,

    # V17.3.5 optional policy-screening constraints. Keep disabled by default
    # unless explicitly activated.
    "min_renewable_local_share_of_electric_demand": None,
    "min_renewable_utilization_rate": None,
    "max_annual_grid_import_share_of_electric_demand": None,

    # Rural/remote low-altitude economy extension. These parameters translate
    # UAV patrol, agricultural plant protection, emergency delivery, forest-fire
    # monitoring and communication-support loads into aggregate planning constraints.
    "min_low_altitude_local_renewable_share": None,
    "enable_remote_low_altitude_microgrid": False,
    "low_altitude_autonomy_hours": 0.0,

    # V17.3.5 StoreMore + net-zero industrial-park extension. Disabled by default
    # so the V17.3.5 county/low-altitude conclusions remain reproducible.
    "min_industrial_park_green_electricity_share": None,
    "carbon_allowance_tco2_per_year": None,

    # V17.3.5 green-electricity direct-supply planning screen.
    # The three alternatives follow the uploaded demonstration logic:
    # 1) park-internal new green power, 2) virtual power plant aggregation,
    # 3) remote green-energy base with dedicated transmission.
    "green_direct_target_share": 0.0,
    "green_direct_planning_years": 20,
    "park_internal_green_lcoe_cny_per_mwh": 320.0,
    "vpp_aggregated_green_lcoe_cny_per_mwh": 395.0,
    "green_base_lcoe_cny_per_mwh": 355.0,
    "park_internal_line_loss_rate": 0.015,
    "vpp_aggregation_loss_rate": 0.025,
    "green_base_transmission_loss_rate": 0.035,
    "park_internal_fixed_cost_million_cny": 6.0,
    "vpp_platform_fixed_cost_million_cny": 9.0,
    "green_base_line_fixed_cost_million_cny": 18.0,

    # V17.3.7投稿导向扩展：Power-to-X/绿氢替代潜力与深度碳管理筛查。
    "enable_p2x_screening": False,
    "p2x_process_heat_substitution_share": 0.0,
    "electrolyzer_specific_consumption_mwh_per_t_h2": 50.0,
    "hydrogen_lhv_mwh_per_t": 33.33,
    "hydrogen_boiler_efficiency": 0.88,
    "green_hydrogen_lcoe_cny_per_mwh": 520.0,
    "carbon_market_price_cny_per_tco2": 215.0,

    # V17.3.9模型深化：将P2X从后处理筛查推进为线性优化中的内生决策。
    "enable_endogenous_p2x": False,
    "p2x_min_process_heat_substitution_share": 0.0,
    "max_electrolyzer_capacity": 80.0,
    "capex_electrolyzer": 850000.0,
    "p2x_variable_om_cost": 4.0,
    "max_p2x_electricity_share_of_renewable_generation": 0.35,

    # Adequacy and emissions
    "reserve_margin": 0.10,
    "pv_capacity_credit": 0.08,
    "wt_capacity_credit": 0.15,
    "grid_emission_factor": 0.55,
    "gas_emission_factor": 0.20,

    # Moderate penalties: the model is allowed to show reasonable curtailment.
    "renewable_curtailment_penalty": 20.0,
    "load_shifting_cost": 30.0,
    "interruptible_load_cost": 1200.0,

    # Reliability economics.  Normal operation no longer hard-fixes unmet load to zero.
    # Instead, critical demand must always be served and non-critical unserved energy
    # is controlled by carrier-specific value-of-lost-load (VOLL) and an annual EENS cap.
    "electric_unserved_energy_penalty": 18000.0,
    "heat_unserved_energy_penalty": 12000.0,
    "cooling_unserved_energy_penalty": 10000.0,
    "max_annual_unserved_energy_ratio": 0.0001,

    # Storage realism
    "battery_degradation_cost": 14.0,
    "thermal_storage_degradation_cost": 2.0,
    "max_battery_equivalent_cycles": 350.0,
    "max_thermal_storage_equivalent_cycles": 365.0,

    # Grid-operation effects
    "grid_demand_charge": 18000.0,
    "grid_smoothing_penalty": 8.0,
    "grid_ramp_limit_per_hour": 30.0,
    "device_smoothing_penalty": 5.0,

    # Flexible load: daily energy-neutral shifting only.
    "max_daily_shift_energy_ratio": 0.06,
    "force_zero_unmet": False,
    "enable_interruptible_load": False,
    "interruptible_load_ratio": 0.0,

    # Equipment ramp rates
    "chp_ramp_rate_per_hour": 0.45,
    "hp_ramp_rate_per_hour": 0.80,
    "ec_ramp_rate_per_hour": 0.80,
    "gb_ramp_rate_per_hour": 0.70,

    # Planning search ranges
    "max_pv_capacity": 220.0,
    "max_wt_capacity": 220.0,
    "max_chp_capacity": 100.0,
    "max_hp_capacity": 150.0,
    "max_ec_capacity": 120.0,
    "max_gb_capacity": 150.0,
    "max_battery_energy_capacity": 300.0,
    "max_battery_power_capacity": 120.0,
    "max_thermal_storage_energy_capacity": 300.0,
    "max_thermal_storage_power_capacity": 120.0,

    "strict_storage_exclusivity": False,
    "storage_dispatch_mode": "optimized",
    "milp_time_limit": 600.0,
    "mip_rel_gap": 0.003,
    "solver_display": False,
}


def get_planning_scenarios_v17_3_1() -> dict[str, dict]:
    """County-scale planning scenarios with county-region-characteristic inputs."""

    base = {
        **COMMON_PARAMS,
        "enable_carbon_constraint": False,
        "internalize_carbon_price": False,
        "enable_battery": False,
        "enable_thermal_storage": False,
        "battery_dispatch_enabled": False,
        "thermal_storage_dispatch_enabled": False,
        "enable_flexible_load": False,
        "shiftable_load_multiplier": 1.0,
        "co2_cap": 1e12,
        "co2_cap_ratio_to_s0": 0.80,
    }

    return {
        "S0": {
            **base,
            "name": "S0 县域基准系统",
            "description": "无碳排放上限、无储能、无柔性负荷。",
        },
        "S1": {
            **base,
            "name": "S1 低碳约束",
            "description": "加入碳排放上限，并在目标中计入碳成本。",
            "enable_carbon_constraint": True,
            "internalize_carbon_price": True,
        },
        "S2": {
            **base,
            "name": "S2 低碳约束+储能",
            "description": "低碳约束下配置电储能和热储能。",
            "enable_carbon_constraint": True,
            "internalize_carbon_price": True,
            "enable_battery": True,
            "enable_thermal_storage": True,
            "battery_dispatch_enabled": True,
            "thermal_storage_dispatch_enabled": True,
        },
        "S3": {
            **base,
            "name": "S3 低碳约束+柔性负荷",
            "description": "低碳约束下允许县域可转移负荷参与调度。",
            "enable_carbon_constraint": True,
            "internalize_carbon_price": True,
            "enable_flexible_load": True,
        },
        "S4": {
            **base,
            "name": "S4 低碳源荷储协同",
            "description": "同时优化储能、柔性负荷和低碳运行。",
            "enable_carbon_constraint": True,
            "internalize_carbon_price": True,
            "enable_battery": True,
            "enable_thermal_storage": True,
            "battery_dispatch_enabled": True,
            "thermal_storage_dispatch_enabled": True,
            "enable_flexible_load": True,
        },
        "S5": {
            **base,
            "name": "S5 偏远低空微电网韧性增强",
            "description": "面向农村和偏远地区低空作业，叠加低空末梢负荷、本地新能源支撑和储能孤岛保障约束。",
            "enable_carbon_constraint": True,
            "internalize_carbon_price": True,
            "enable_battery": True,
            "enable_thermal_storage": True,
            "battery_dispatch_enabled": True,
            "thermal_storage_dispatch_enabled": True,
            "enable_flexible_load": True,
            "min_low_altitude_local_renewable_share": 1.0,
            "enable_remote_low_altitude_microgrid": True,
            "low_altitude_autonomy_hours": 4.0,
        },
        "S6": {
            **base,
            "name": "S6 县域产业园区净零协同增强",
            "description": "在县域综合能源系统中补充净零产业园区视角，强化工商业园区绿色电力覆盖、碳成本内化、储能和柔性负荷协同。",
            "enable_carbon_constraint": True,
            "internalize_carbon_price": True,
            "enable_battery": True,
            "enable_thermal_storage": True,
            "battery_dispatch_enabled": True,
            "thermal_storage_dispatch_enabled": True,
            "enable_flexible_load": True,
            "min_industrial_park_green_electricity_share": 0.75,
            "green_direct_target_share": 0.75,
            "min_renewable_utilization_rate": 0.72,
            "co2_cap_ratio_to_s0": 0.40,
        },

        "S7": {
            **base,
            "name": "S7 低空经济—产业园区—绿电直连综合增强",
            "description": "面向答辩展示和综合应用，把偏远低空作业、县域产业园区净零、光储充微电网韧性和绿电直连补充方式统一到同一规划筛查场景。",
            "enable_carbon_constraint": True,
            "internalize_carbon_price": True,
            "enable_battery": True,
            "enable_thermal_storage": True,
            "battery_dispatch_enabled": True,
            "thermal_storage_dispatch_enabled": True,
            "enable_flexible_load": True,
            "min_low_altitude_local_renewable_share": 1.0,
            "enable_remote_low_altitude_microgrid": True,
            "low_altitude_autonomy_hours": 5.0,
            "min_industrial_park_green_electricity_share": 0.80,
            "green_direct_target_share": 0.80,
            "min_renewable_utilization_rate": 0.75,
            "co2_cap_ratio_to_s0": 0.36,
            "max_annual_grid_import_share_of_electric_demand": 0.55,
        },
        "S8": {
            **base,
            "name": "S8 投稿导向零碳园区深度脱碳",
            "description": "面向Applied Energy零碳工业园区专题，进一步强化园区绿电覆盖、碳配额压力、绿电直连、低空韧性，并将Power-to-X/绿氢替代从诊断筛查推进为优化内生决策。",
            "enable_carbon_constraint": True,
            "internalize_carbon_price": True,
            "enable_battery": True,
            "enable_thermal_storage": True,
            "battery_dispatch_enabled": True,
            "thermal_storage_dispatch_enabled": True,
            "enable_flexible_load": True,
            "min_low_altitude_local_renewable_share": 1.0,
            "enable_remote_low_altitude_microgrid": True,
            "low_altitude_autonomy_hours": 6.0,
            "min_industrial_park_green_electricity_share": 0.85,
            "green_direct_target_share": 0.90,
            "min_renewable_utilization_rate": 0.78,
            "co2_cap_ratio_to_s0": 0.35,
            "max_annual_grid_import_share_of_electric_demand": 0.45,
            "carbon_allowance_tco2_per_year": 9500.0,
            "enable_p2x_screening": True,
            "p2x_process_heat_substitution_share": 0.20,
            "enable_endogenous_p2x": True,
            "p2x_min_process_heat_substitution_share": 0.10,
            "max_electrolyzer_capacity": 70.0,
            "capex_electrolyzer": 820000.0,
            "p2x_variable_om_cost": 4.0,
            "max_p2x_electricity_share_of_renewable_generation": 0.32,
            "green_hydrogen_lcoe_cny_per_mwh": 520.0,
        },
    }


def get_operation_scenarios_v17_3_1(
    fixed_capacities: dict[str, float],
    co2_cap: float = 1e12,
) -> dict[str, dict]:
    """Fixed-capacity operation comparisons.

    R0/R2 receive deterministic rule profiles from paper_run_v17_3_1_county.py.
    R1/R3/R4 optimize storage dispatch.  All operation cases enforce strict
    storage and grid import/export exclusivity.
    """

    base = {
        **COMMON_PARAMS,
        "fixed_capacities": deepcopy(fixed_capacities),
        "enable_battery": fixed_capacities.get("C_BAT_E", 0.0) > 1e-9,
        "enable_thermal_storage": fixed_capacities.get("C_TS_E", 0.0) > 1e-9,
        "battery_dispatch_enabled": True,
        "thermal_storage_dispatch_enabled": True,
        "enable_flexible_load": False,
        "enable_carbon_constraint": False,
        "internalize_carbon_price": False,
        "co2_cap": float(co2_cap),
        "strict_storage_exclusivity": True,
        "strict_grid_exchange_exclusivity": True,
        "storage_dispatch_mode": "optimized",
        "r4_cap_ratio_to_r3": 0.97,
    }

    return {
        "R0": {
            **base,
            "name": "R0 同容量常规规则运行",
            "description": "固定S4容量，采用预设储能规则曲线，柔性负荷不响应。",
        },
        "R1": {
            **base,
            "name": "R1 同容量储能优化调度",
            "description": "固定S4容量，仅将储能由规则控制改为优化调度。",
        },
        "R2": {
            **base,
            "name": "R2 规则储能+柔性负荷",
            "description": "固定S4容量，储能采用规则曲线，并加入可转移负荷。",
            "enable_flexible_load": True,
        },
        "R3": {
            **base,
            "name": "R3 源荷储经济协同调度",
            "description": "固定S4容量，储能和柔性负荷共同优化，不计碳价且不设碳上限。",
            "enable_flexible_load": True,
        },
        "R4": {
            **base,
            "name": "R4 源荷储低碳协同调度",
            "description": "固定S4容量，储能和柔性负荷共同优化，并计入碳外部成本和更严格的碳排放上限。",
            "enable_flexible_load": True,
            "enable_carbon_constraint": True,
            "internalize_carbon_price": True,
        },
    }


def get_reliability_stress_scenarios_v17_3_1(
    fixed_capacities: dict[str, float],
) -> dict[str, dict]:
    """Reliability-screening cases using the same fixed S4 capacities.

    Grid availability and renewable/load stress are applied in
    reliability_run_v17_3_1_county.py.  The annual EENS cap is disabled in
    these one-day stress tests so the model can reveal physically unavoidable
    non-critical shortages rather than becoming infeasible.
    """

    base = {
        **COMMON_PARAMS,
        "fixed_capacities": deepcopy(fixed_capacities),
        "enable_battery": fixed_capacities.get("C_BAT_E", 0.0) > 1e-9,
        "enable_thermal_storage": fixed_capacities.get("C_TS_E", 0.0) > 1e-9,
        "battery_dispatch_enabled": True,
        "thermal_storage_dispatch_enabled": True,
        "enable_flexible_load": True,
        "enable_carbon_constraint": False,
        "internalize_carbon_price": True,
        "strict_storage_exclusivity": True,
        "strict_grid_exchange_exclusivity": True,
        "storage_dispatch_mode": "optimized",
        "force_zero_unmet": False,
        "max_annual_unserved_energy_ratio": None,
        "enforce_planning_adequacy": False,
        "enable_grid_export": False,
        "grid_export_capacity": 0.0,
    }

    return {
        "Q0": {**base, "name": "Q0 正常运行日"},
        "Q1": {**base, "name": "Q1 春灌高负荷—主网降额中等扰动"},
        "Q2": {**base, "name": "Q2 冬季采暖—低风光中等扰动"},
        "Q3": {**base, "name": "Q3 冬季高负荷—低风光—主网严重降额"},
    }


if __name__ == "__main__":
    for key, value in get_planning_scenarios_v17_3_1().items():
        print(key, value["name"])
