from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class ConfigurationIssue:
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class IntegratedPlanningConfig:
    scenario_key: str
    n_steps_per_hour: int
    seed: int
    max_pv_capacity: float
    max_wt_capacity: float
    max_chp_capacity: float
    max_hp_capacity: float
    max_ec_capacity: float
    max_gb_capacity: float
    enable_battery: bool
    enable_thermal_storage: bool
    max_battery_energy_capacity: float
    max_battery_power_capacity: float
    max_thermal_storage_energy_capacity: float
    max_thermal_storage_power_capacity: float
    enable_flexible_load: bool
    max_daily_shift_energy_ratio: float
    enable_interruptible_load: bool
    interruptible_load_ratio: float
    enable_carbon_constraint: bool
    internalize_carbon_price: bool
    co2_cap_ratio_to_s0: float
    carbon_market_price_cny_per_tco2: float
    min_industrial_park_green_electricity_share: float
    green_direct_target_share: float
    min_renewable_utilization_rate: float
    enable_endogenous_p2x: bool
    p2x_min_process_heat_substitution_share: float
    max_electrolyzer_capacity: float
    max_p2x_electricity_share_of_renewable_generation: float

    @classmethod
    def from_scenario(
        cls,
        scenario_key: str,
        scenario: dict[str, Any],
        n_steps_per_hour: int = 1,
        seed: int = 42,
    ) -> "IntegratedPlanningConfig":
        def number(name: str, default: float = 0.0) -> float:
            value = scenario.get(name, default)
            return default if value is None else float(value)

        return cls(
            scenario_key=scenario_key.upper().strip(),
            n_steps_per_hour=n_steps_per_hour,
            seed=seed,
            max_pv_capacity=number("max_pv_capacity", 220.0),
            max_wt_capacity=number("max_wt_capacity", 220.0),
            max_chp_capacity=number("max_chp_capacity", 100.0),
            max_hp_capacity=number("max_hp_capacity", 150.0),
            max_ec_capacity=number("max_ec_capacity", 120.0),
            max_gb_capacity=number("max_gb_capacity", 150.0),
            enable_battery=bool(scenario.get("enable_battery", False)),
            enable_thermal_storage=bool(scenario.get("enable_thermal_storage", False)),
            max_battery_energy_capacity=number("max_battery_energy_capacity", 300.0),
            max_battery_power_capacity=number("max_battery_power_capacity", 120.0),
            max_thermal_storage_energy_capacity=number("max_thermal_storage_energy_capacity", 300.0),
            max_thermal_storage_power_capacity=number("max_thermal_storage_power_capacity", 120.0),
            enable_flexible_load=bool(scenario.get("enable_flexible_load", False)),
            max_daily_shift_energy_ratio=number("max_daily_shift_energy_ratio", 0.06),
            enable_interruptible_load=bool(scenario.get("enable_interruptible_load", False)),
            interruptible_load_ratio=number("interruptible_load_ratio", 0.0),
            enable_carbon_constraint=bool(scenario.get("enable_carbon_constraint", False)),
            internalize_carbon_price=bool(scenario.get("internalize_carbon_price", False)),
            co2_cap_ratio_to_s0=number("co2_cap_ratio_to_s0", 0.8),
            carbon_market_price_cny_per_tco2=number("carbon_market_price_cny_per_tco2", 215.0),
            min_industrial_park_green_electricity_share=number(
                "min_industrial_park_green_electricity_share", 0.0
            ),
            green_direct_target_share=number("green_direct_target_share", 0.0),
            min_renewable_utilization_rate=number("min_renewable_utilization_rate", 0.0),
            enable_endogenous_p2x=bool(scenario.get("enable_endogenous_p2x", False)),
            p2x_min_process_heat_substitution_share=number(
                "p2x_min_process_heat_substitution_share", 0.0
            ),
            max_electrolyzer_capacity=number("max_electrolyzer_capacity", 80.0),
            max_p2x_electricity_share_of_renewable_generation=number(
                "max_p2x_electricity_share_of_renewable_generation", 0.35
            ),
        )

    def validate(self) -> list[ConfigurationIssue]:
        issues: list[ConfigurationIssue] = []
        if self.scenario_key not in {f"S{index}" for index in range(9)}:
            issues.append(ConfigurationIssue("scenario_key", "规划场景必须是S0至S8"))
        if self.n_steps_per_hour not in {1, 2, 4}:
            issues.append(ConfigurationIssue("n_steps_per_hour", "时间分辨率只支持60、30或15分钟"))
        if self.seed < 0:
            issues.append(ConfigurationIssue("seed", "随机种子不能小于0"))

        capacity_fields = {
            "max_pv_capacity": self.max_pv_capacity,
            "max_wt_capacity": self.max_wt_capacity,
            "max_chp_capacity": self.max_chp_capacity,
            "max_hp_capacity": self.max_hp_capacity,
            "max_ec_capacity": self.max_ec_capacity,
            "max_gb_capacity": self.max_gb_capacity,
            "max_battery_energy_capacity": self.max_battery_energy_capacity,
            "max_battery_power_capacity": self.max_battery_power_capacity,
            "max_thermal_storage_energy_capacity": self.max_thermal_storage_energy_capacity,
            "max_thermal_storage_power_capacity": self.max_thermal_storage_power_capacity,
            "max_electrolyzer_capacity": self.max_electrolyzer_capacity,
        }
        for field_name, value in capacity_fields.items():
            if value < 0:
                issues.append(ConfigurationIssue(field_name, "容量上限不能小于0"))
        if self.enable_battery and (
            self.max_battery_energy_capacity <= 0 or self.max_battery_power_capacity <= 0
        ):
            issues.append(ConfigurationIssue("battery", "启用电储能时，能量和功率上限必须大于0"))
        if self.enable_thermal_storage and (
            self.max_thermal_storage_energy_capacity <= 0 or self.max_thermal_storage_power_capacity <= 0
        ):
            issues.append(ConfigurationIssue("thermal_storage", "启用热储能时，能量和功率上限必须大于0"))

        ratio_fields = {
            "max_daily_shift_energy_ratio": self.max_daily_shift_energy_ratio,
            "interruptible_load_ratio": self.interruptible_load_ratio,
            "co2_cap_ratio_to_s0": self.co2_cap_ratio_to_s0,
            "min_industrial_park_green_electricity_share": self.min_industrial_park_green_electricity_share,
            "green_direct_target_share": self.green_direct_target_share,
            "min_renewable_utilization_rate": self.min_renewable_utilization_rate,
            "p2x_min_process_heat_substitution_share": self.p2x_min_process_heat_substitution_share,
            "max_p2x_electricity_share_of_renewable_generation": (
                self.max_p2x_electricity_share_of_renewable_generation
            ),
        }
        for field_name, value in ratio_fields.items():
            if not 0.0 <= value <= 1.0:
                issues.append(ConfigurationIssue(field_name, "比例必须在0至100%之间"))
        if self.enable_flexible_load and self.max_daily_shift_energy_ratio <= 0:
            issues.append(ConfigurationIssue("max_daily_shift_energy_ratio", "启用柔性负荷时日内可转移比例必须大于0"))
        if self.enable_interruptible_load and self.interruptible_load_ratio <= 0:
            issues.append(ConfigurationIssue("interruptible_load_ratio", "启用可中断负荷时可中断比例必须大于0"))
        if self.enable_carbon_constraint and not 0 < self.co2_cap_ratio_to_s0 <= 1:
            issues.append(ConfigurationIssue("co2_cap_ratio_to_s0", "启用碳约束时碳排上限比例必须大于0且不超过100%"))
        if self.carbon_market_price_cny_per_tco2 < 0:
            issues.append(ConfigurationIssue("carbon_market_price_cny_per_tco2", "碳价不能小于0"))
        if self.enable_endogenous_p2x:
            if self.max_electrolyzer_capacity <= 0:
                issues.append(ConfigurationIssue("max_electrolyzer_capacity", "启用P2X时电解槽容量上限必须大于0"))
            if self.p2x_min_process_heat_substitution_share <= 0:
                issues.append(
                    ConfigurationIssue("p2x_min_process_heat_substitution_share", "启用P2X时工艺热替代比例必须大于0")
                )
        return issues

    def to_payload(self) -> dict[str, Any]:
        values = asdict(self)
        overrides = {
            name: values[name]
            for name in values
            if name not in {"scenario_key", "n_steps_per_hour", "seed"}
        }
        overrides.update(
            {
                "battery_dispatch_enabled": self.enable_battery,
                "thermal_storage_dispatch_enabled": self.enable_thermal_storage,
            }
        )
        return {
            "schema_version": "integrated-planning-v1",
            "model_kind": "integrated_planning",
            "scenario_key": self.scenario_key,
            "n_steps_per_hour": self.n_steps_per_hour,
            "seed": self.seed,
            "overrides": overrides,
        }


def scenario_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
