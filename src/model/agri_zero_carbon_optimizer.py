from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from src.core.agri_parameter_registry import phase1_parameter_value
from src.model.agri_park_profiles import validate_agri_park_profiles


FLOW_BLOCKS = (
    "pv_to_load",
    "pv_to_battery",
    "pv_export",
    "pv_curtailment",
    "direct_to_load",
    "direct_to_battery",
    "direct_export",
    "direct_curtailment",
    "battery_discharge_pv",
    "battery_discharge_direct",
    "soc_pv",
    "soc_direct",
    "grid_to_load",
    "irrigation_flexible",
    "processing_flexible",
    "storage_flexible",
)


@dataclass(frozen=True, slots=True)
class AgriOptimizationRequest:
    target_physical_green_share: float = 1.0
    planning_interval_hours: int = 1
    allow_local_pv: bool = True
    allow_green_direct: bool = True
    allow_battery: bool = True
    allow_export: bool = True
    fixed_pv_capacity_mw: float | None = None
    fixed_green_direct_capacity_mw: float | None = None
    fixed_battery_power_mw: float | None = None
    fixed_battery_energy_mwh: float | None = None


@dataclass(frozen=True, slots=True)
class AgriOptimizationResult:
    success: bool
    status: str
    strategy_name: str
    capacities: dict[str, float]
    summary: dict[str, float]
    cost_breakdown: dict[str, float]
    dispatch: pd.DataFrame


class _ConstraintBuilder:
    def __init__(self, variable_count: int) -> None:
        self.variable_count = variable_count
        self.eq_rows: list[int] = []
        self.eq_cols: list[int] = []
        self.eq_data: list[float] = []
        self.eq_rhs: list[float] = []
        self.ub_rows: list[int] = []
        self.ub_cols: list[int] = []
        self.ub_data: list[float] = []
        self.ub_rhs: list[float] = []

    def equality(self, terms: Iterable[tuple[int, float]], rhs: float) -> None:
        row = len(self.eq_rhs)
        for column, value in terms:
            if value:
                self.eq_rows.append(row)
                self.eq_cols.append(column)
                self.eq_data.append(float(value))
        self.eq_rhs.append(float(rhs))

    def upper_bound(self, terms: Iterable[tuple[int, float]], rhs: float) -> None:
        row = len(self.ub_rhs)
        for column, value in terms:
            if value:
                self.ub_rows.append(row)
                self.ub_cols.append(column)
                self.ub_data.append(float(value))
        self.ub_rhs.append(float(rhs))

    def matrices(self) -> tuple[coo_matrix, np.ndarray, coo_matrix, np.ndarray]:
        equality = coo_matrix(
            (self.eq_data, (self.eq_rows, self.eq_cols)),
            shape=(len(self.eq_rhs), self.variable_count),
        ).tocsr()
        upper = coo_matrix(
            (self.ub_data, (self.ub_rows, self.ub_cols)),
            shape=(len(self.ub_rhs), self.variable_count),
        ).tocsr()
        return equality, np.asarray(self.eq_rhs), upper, np.asarray(self.ub_rhs)


class AgriZeroCarbonOptimizer:
    """农业园区全年连续时序容量规划与运行联合优化。

    绿电直连固定工程费通过“未建设”和“已建设”两个连续线性规划分别求解后比较，
    避免在8760小时模型中引入大量整数变量。储能只接收已核验的本地光伏和直连绿电，
    因而放电来源可以逐时分账，公共电网电量不会被误计为绿电。
    """

    GLOBAL_VARIABLES = ("pv_capacity", "direct_capacity", "battery_power", "battery_energy", "grid_peak")

    def optimize(
        self,
        profiles: pd.DataFrame,
        request: AgriOptimizationRequest | None = None,
    ) -> AgriOptimizationResult:
        request = request or AgriOptimizationRequest()
        self._validate_request(request)
        issues = validate_agri_park_profiles(profiles)
        if issues:
            raise ValueError("；".join(issues))
        self._validate_no_arbitrage_conditions(profiles)
        planning_profiles = self._aggregate_for_planning(profiles, request.planning_interval_hours)
        candidates: list[AgriOptimizationResult] = []
        if request.fixed_green_direct_capacity_mw is not None:
            candidates.append(
                self._solve_case(
                    planning_profiles,
                    request,
                    direct_enabled=request.fixed_green_direct_capacity_mw > 0.0,
                )
            )
        else:
            candidates.append(self._solve_case(planning_profiles, request, direct_enabled=False))
            if request.allow_green_direct:
                candidates.append(self._solve_case(planning_profiles, request, direct_enabled=True))
        feasible = [candidate for candidate in candidates if candidate.success]
        if not feasible:
            status = "；".join(candidate.status for candidate in candidates)
            return self._failure_result(f"没有满足目标的可行方案：{status}")
        return min(feasible, key=lambda candidate: candidate.summary["annual_total_cost_cny"])

    @staticmethod
    def _validate_request(request: AgriOptimizationRequest) -> None:
        if not 0.0 <= request.target_physical_green_share <= 1.0:
            raise ValueError("物理绿电匹配目标必须位于0至1之间")
        if request.planning_interval_hours not in {1, 2, 3, 4, 6}:
            raise ValueError("容量规划时间间隔只支持1、2、3、4或6小时")
        fixed_capacities = {
            "固定光伏容量": request.fixed_pv_capacity_mw,
            "固定绿电直连容量": request.fixed_green_direct_capacity_mw,
            "固定储能功率": request.fixed_battery_power_mw,
            "固定储能容量": request.fixed_battery_energy_mwh,
        }
        for name, value in fixed_capacities.items():
            if value is not None and value < 0.0:
                raise ValueError(f"{name}不能小于0")
        fixed_limits = (
            ("固定光伏容量", request.fixed_pv_capacity_mw, "pv.agri_planning_max_capacity_mw"),
            (
                "固定绿电直连容量",
                request.fixed_green_direct_capacity_mw,
                "green_direct.max_capacity_mw",
            ),
            ("固定储能功率", request.fixed_battery_power_mw, "battery.agri_planning_max_power_mw"),
            ("固定储能容量", request.fixed_battery_energy_mwh, "battery.agri_planning_max_energy_mwh"),
        )
        for name, value, limit_code in fixed_limits:
            if value is not None and value > phase1_parameter_value(limit_code) + 1e-9:
                raise ValueError(f"{name}超过农业园区规划边界")

    @staticmethod
    def _validate_no_arbitrage_conditions(profiles: pd.DataFrame) -> None:
        wheeling = phase1_parameter_value("grid.export_wheeling_cny_per_mwh")
        import_price = profiles["grid_buy_price_cny_per_mwh"].to_numpy(dtype=float)
        net_export_price = np.maximum(
            profiles["grid_sell_price_cny_per_mwh"].to_numpy(dtype=float) - wheeling,
            0.0,
        )
        if np.any(import_price <= net_export_price):
            raise ValueError("购电价格必须严格高于同期净外送价格，否则需要启用购售电整数互斥约束")
        degradation = phase1_parameter_value("battery.degradation_cny_per_mwh")
        curtailment_penalty = phase1_parameter_value("pv.curtailment_penalty_cny_per_mwh")
        if degradation <= curtailment_penalty:
            raise ValueError("储能放电衰减成本必须高于弃电惩罚，否则需要启用充放电整数互斥约束")
        if "grid_import_availability_pu" in profiles and not profiles[
            "grid_import_availability_pu"
        ].between(0.0, 1.0).all():
            raise ValueError("公共电网可用率必须位于0至1之间")

    @staticmethod
    def _aggregate_for_planning(profiles: pd.DataFrame, interval_hours: int) -> pd.DataFrame:
        if interval_hours == 1:
            return profiles.copy().reset_index(drop=True)
        data = profiles.copy()
        data["timestamp"] = pd.to_datetime(data["timestamp"])
        numeric_columns = [
            column
            for column in data.select_dtypes(include=[np.number]).columns
            if column != "resolution_minutes"
        ]
        text_columns = [
            column for column in data.columns if column not in numeric_columns and column != "timestamp"
        ]
        aggregation = {column: "mean" for column in numeric_columns}
        aggregation.update({column: "first" for column in text_columns})
        result = (
            data.set_index("timestamp")
            .resample(f"{interval_hours}h", label="left", closed="left")
            .agg(aggregation)
            .reset_index()
        )
        result["resolution_minutes"] = interval_hours * 60
        return result

    def _solve_case(
        self,
        profiles: pd.DataFrame,
        request: AgriOptimizationRequest,
        *,
        direct_enabled: bool,
    ) -> AgriOptimizationResult:
        data = profiles.copy().reset_index(drop=True)
        timestamps = pd.to_datetime(data["timestamp"])
        dt = self._time_step_hours(timestamps, data)
        n = len(data)
        global_count = len(self.GLOBAL_VARIABLES)
        variable_count = global_count + len(FLOW_BLOCKS) * n
        global_index = {name: index for index, name in enumerate(self.GLOBAL_VARIABLES)}
        block_index = {
            name: np.arange(global_count + block * n, global_count + (block + 1) * n, dtype=int)
            for block, name in enumerate(FLOW_BLOCKS)
        }

        objective = np.zeros(variable_count, dtype=float)
        lower = np.zeros(variable_count, dtype=float)
        upper = np.full(variable_count, inf, dtype=float)
        self._set_capacity_bounds(lower, upper, global_index, request, direct_enabled)
        self._set_flexible_load_bounds(data, upper, block_index)
        annualization = self._capital_recovery_factor()
        fixed_om = phase1_parameter_value("finance.fixed_om_rate")
        objective[global_index["pv_capacity"]] = phase1_parameter_value("pv.capex_cny_per_mw") * (
            annualization + fixed_om
        )
        objective[global_index["battery_power"]] = phase1_parameter_value(
            "battery.capex_power_cny_per_mw"
        ) * (annualization + fixed_om)
        objective[global_index["battery_energy"]] = phase1_parameter_value(
            "battery.capex_energy_cny_per_mwh"
        ) * (annualization + fixed_om)
        objective[global_index["grid_peak"]] = phase1_parameter_value(
            "grid.agri_demand_charge_cny_per_mw_year"
        )

        carbon_price = phase1_parameter_value("carbon.price_cny_per_tco2")
        direct_loss = phase1_parameter_value("green_direct.base_loss_rate")
        direct_price = phase1_parameter_value("green_direct.base_lcoe_cny_per_mwh")
        degradation = phase1_parameter_value("battery.degradation_cny_per_mwh")
        curtailment_penalty = phase1_parameter_value("pv.curtailment_penalty_cny_per_mwh")
        wheeling = phase1_parameter_value("grid.export_wheeling_cny_per_mwh")
        buy_price = data["grid_buy_price_cny_per_mwh"].to_numpy(dtype=float)
        sell_price = data["grid_sell_price_cny_per_mwh"].to_numpy(dtype=float)
        emission_factor = data["grid_emission_factor_tco2_per_mwh"].to_numpy(dtype=float)
        objective[block_index["grid_to_load"]] = dt * (buy_price + carbon_price * emission_factor)
        for block in ("direct_to_load", "direct_to_battery", "direct_export", "direct_curtailment"):
            objective[block_index[block]] = dt * direct_price / (1.0 - direct_loss)
        for block in ("battery_discharge_pv", "battery_discharge_direct"):
            objective[block_index[block]] = dt * degradation
        objective[block_index["pv_curtailment"]] = dt * curtailment_penalty
        objective[block_index["direct_curtailment"]] += dt * curtailment_penalty
        objective[block_index["pv_export"]] = -dt * np.maximum(sell_price - wheeling, 0.0)
        objective[block_index["direct_export"]] += -dt * np.maximum(sell_price - wheeling, 0.0)

        constraints = _ConstraintBuilder(variable_count)
        self._add_hourly_constraints(data, dt, global_index, block_index, constraints)
        self._add_flexible_energy_constraints(data, dt, block_index, constraints)
        annual_demand = float(data["total_meter_load_mw"].sum() * dt)
        constraints.upper_bound(
            ((int(index), dt) for index in block_index["grid_to_load"]),
            (1.0 - request.target_physical_green_share) * annual_demand,
        )
        usable_soc = phase1_parameter_value("battery.soc_max") - phase1_parameter_value("battery.soc_min")
        max_cycles = phase1_parameter_value("battery.max_equivalent_cycles")
        constraints.upper_bound(
            [
                *((int(index), dt) for index in block_index["battery_discharge_pv"]),
                *((int(index), dt) for index in block_index["battery_discharge_direct"]),
                (global_index["battery_energy"], -max_cycles * usable_soc),
            ],
            0.0,
        )
        constraints.upper_bound(
            ((global_index["battery_power"], 1.0), (global_index["battery_energy"], -1.0)),
            0.0,
        )
        constraints.upper_bound(
            ((global_index["battery_energy"], 1.0), (global_index["battery_power"], -4.0)),
            0.0,
        )
        a_eq, b_eq, a_ub, b_ub = constraints.matrices()
        solution = linprog(
            objective,
            A_ub=a_ub,
            b_ub=b_ub,
            A_eq=a_eq,
            b_eq=b_eq,
            bounds=list(zip(lower, upper, strict=True)),
            method="highs",
            options={"presolve": True},
        )
        if not solution.success:
            label = "建设直连" if direct_enabled else "不建设直连"
            return self._failure_result(f"{label}方案求解失败：{solution.message}")

        fixed_direct_annual = 0.0
        if direct_enabled and solution.x[global_index["direct_capacity"]] > 1e-7:
            fixed_direct_annual = phase1_parameter_value("green_direct.base_fixed_cost_cny") * (
                annualization + fixed_om
            )
        return self._build_result(
            data,
            dt,
            solution.x,
            objective,
            global_index,
            block_index,
            fixed_direct_annual,
            request,
        )

    @staticmethod
    def _time_step_hours(timestamps: pd.Series, data: pd.DataFrame) -> float:
        if len(timestamps) > 1:
            return float(timestamps.diff().dropna().dt.total_seconds().median()) / 3600.0
        return float(data.get("resolution_minutes", pd.Series([60.0])).iloc[0]) / 60.0

    @staticmethod
    def _capital_recovery_factor() -> float:
        years = phase1_parameter_value("finance.planning_years")
        rate = phase1_parameter_value("finance.discount_rate")
        if rate == 0.0:
            return 1.0 / years
        factor = (1.0 + rate) ** years
        return rate * factor / (factor - 1.0)

    @staticmethod
    def _set_capacity_bounds(
        lower: np.ndarray,
        upper: np.ndarray,
        index: dict[str, int],
        request: AgriOptimizationRequest,
        direct_enabled: bool,
    ) -> None:
        upper[index["pv_capacity"]] = (
            phase1_parameter_value("pv.agri_planning_max_capacity_mw") if request.allow_local_pv else 0.0
        )
        if direct_enabled and request.allow_green_direct:
            lower[index["direct_capacity"]] = phase1_parameter_value(
                "green_direct.minimum_contract_capacity_mw"
            )
            upper[index["direct_capacity"]] = phase1_parameter_value("green_direct.max_capacity_mw")
        else:
            upper[index["direct_capacity"]] = 0.0
        upper[index["battery_power"]] = (
            phase1_parameter_value("battery.agri_planning_max_power_mw") if request.allow_battery else 0.0
        )
        upper[index["battery_energy"]] = (
            phase1_parameter_value("battery.agri_planning_max_energy_mwh") if request.allow_battery else 0.0
        )
        upper[index["grid_peak"]] = phase1_parameter_value("grid.agri_import_capacity_mw")
        fixed = {
            "pv_capacity": request.fixed_pv_capacity_mw,
            "direct_capacity": request.fixed_green_direct_capacity_mw,
            "battery_power": request.fixed_battery_power_mw,
            "battery_energy": request.fixed_battery_energy_mwh,
        }
        for name, value in fixed.items():
            if value is not None:
                lower[index[name]] = float(value)
                upper[index[name]] = float(value)

    @staticmethod
    def _set_flexible_load_bounds(
        data: pd.DataFrame,
        upper: np.ndarray,
        blocks: dict[str, np.ndarray],
    ) -> None:
        specifications = (
            ("irrigation_flexible", "irrigation_load_mw", "load.irrigation.flexible_share", "load.irrigation.peak_mw"),
            ("processing_flexible", "grain_processing_load_mw", "load.processing.flexible_share", "load.processing.peak_mw"),
            ("storage_flexible", "storage_cold_chain_load_mw", "load.storage.flexible_share", None),
        )
        for block, column, share_code, peak_code in specifications:
            share = phase1_parameter_value(share_code)
            baseline = data[column].to_numpy(dtype=float)
            peak = phase1_parameter_value(peak_code) if peak_code else 0.65
            upper[blocks[block]] = np.maximum(peak - (1.0 - share) * baseline, 0.0)

    @staticmethod
    def _add_hourly_constraints(
        data: pd.DataFrame,
        dt: float,
        global_index: dict[str, int],
        blocks: dict[str, np.ndarray],
        constraints: _ConstraintBuilder,
    ) -> None:
        n = len(data)
        pv_cf = data["pv_availability_pu"].to_numpy(dtype=float)
        direct_reference = phase1_parameter_value("green_direct.max_capacity_mw")
        direct_cf = np.clip(data["direct_green_available_mw"].to_numpy(dtype=float) / direct_reference, 0.0, 1.0)
        direct_delivery_cf = direct_cf * (1.0 - phase1_parameter_value("green_direct.base_loss_rate"))
        charge_efficiency = phase1_parameter_value("battery.charge_efficiency")
        discharge_efficiency = phase1_parameter_value("battery.discharge_efficiency")
        retention = 1.0 - phase1_parameter_value("battery.self_discharge_per_hour") * dt
        usable_soc = phase1_parameter_value("battery.soc_max") - phase1_parameter_value("battery.soc_min")
        import_capacity = phase1_parameter_value("grid.agri_import_capacity_mw")
        grid_availability = (
            data["grid_import_availability_pu"].to_numpy(dtype=float)
            if "grid_import_availability_pu" in data
            else np.ones(n, dtype=float)
        )
        export_capacity = phase1_parameter_value("grid.demo_export_capacity_mw")
        irrigation_share = phase1_parameter_value("load.irrigation.flexible_share")
        processing_share = phase1_parameter_value("load.processing.flexible_share")
        storage_share = phase1_parameter_value("load.storage.flexible_share")
        fixed_load = (
            data["public_auxiliary_load_mw"].to_numpy(dtype=float)
            + (1.0 - irrigation_share) * data["irrigation_load_mw"].to_numpy(dtype=float)
            + (1.0 - processing_share) * data["grain_processing_load_mw"].to_numpy(dtype=float)
            + (1.0 - storage_share) * data["storage_cold_chain_load_mw"].to_numpy(dtype=float)
        )
        for t in range(n):
            constraints.equality(
                (
                    (int(blocks["pv_to_load"][t]), 1.0),
                    (int(blocks["pv_to_battery"][t]), 1.0),
                    (int(blocks["pv_export"][t]), 1.0),
                    (int(blocks["pv_curtailment"][t]), 1.0),
                    (global_index["pv_capacity"], -pv_cf[t]),
                ),
                0.0,
            )
            constraints.equality(
                (
                    (int(blocks["direct_to_load"][t]), 1.0),
                    (int(blocks["direct_to_battery"][t]), 1.0),
                    (int(blocks["direct_export"][t]), 1.0),
                    (int(blocks["direct_curtailment"][t]), 1.0),
                    (global_index["direct_capacity"], -direct_delivery_cf[t]),
                ),
                0.0,
            )
            constraints.equality(
                (
                    (int(blocks["pv_to_load"][t]), 1.0),
                    (int(blocks["direct_to_load"][t]), 1.0),
                    (int(blocks["battery_discharge_pv"][t]), 1.0),
                    (int(blocks["battery_discharge_direct"][t]), 1.0),
                    (int(blocks["grid_to_load"][t]), 1.0),
                    (int(blocks["irrigation_flexible"][t]), -1.0),
                    (int(blocks["processing_flexible"][t]), -1.0),
                    (int(blocks["storage_flexible"][t]), -1.0),
                ),
                fixed_load[t],
            )
            previous = (t - 1) % n
            constraints.equality(
                (
                    (int(blocks["soc_pv"][t]), 1.0),
                    (int(blocks["soc_pv"][previous]), -retention),
                    (int(blocks["pv_to_battery"][t]), -charge_efficiency * dt),
                    (int(blocks["battery_discharge_pv"][t]), dt / discharge_efficiency),
                ),
                0.0,
            )
            constraints.equality(
                (
                    (int(blocks["soc_direct"][t]), 1.0),
                    (int(blocks["soc_direct"][previous]), -retention),
                    (int(blocks["direct_to_battery"][t]), -charge_efficiency * dt),
                    (int(blocks["battery_discharge_direct"][t]), dt / discharge_efficiency),
                ),
                0.0,
            )
            constraints.upper_bound(
                (
                    (int(blocks["pv_to_battery"][t]), 1.0),
                    (int(blocks["direct_to_battery"][t]), 1.0),
                    (global_index["battery_power"], -1.0),
                ),
                0.0,
            )
            constraints.upper_bound(
                (
                    (int(blocks["battery_discharge_pv"][t]), 1.0),
                    (int(blocks["battery_discharge_direct"][t]), 1.0),
                    (global_index["battery_power"], -1.0),
                ),
                0.0,
            )
            constraints.upper_bound(
                (
                    (int(blocks["soc_pv"][t]), 1.0),
                    (int(blocks["soc_direct"][t]), 1.0),
                    (global_index["battery_energy"], -usable_soc),
                ),
                0.0,
            )
            constraints.upper_bound(
                (
                    (int(blocks["grid_to_load"][t]), 1.0),
                    (global_index["grid_peak"], -1.0),
                ),
                0.0,
            )
            constraints.upper_bound(
                ((int(blocks["grid_to_load"][t]), 1.0),),
                import_capacity * max(0.0, min(grid_availability[t], 1.0)),
            )
            constraints.upper_bound(
                (
                    (int(blocks["pv_export"][t]), 1.0),
                    (int(blocks["direct_export"][t]), 1.0),
                ),
                export_capacity,
            )
            constraints.upper_bound(
                (
                    (int(blocks["grid_to_load"][t]), 1.0),
                    (int(blocks["direct_to_load"][t]), 1.0),
                    (int(blocks["direct_to_battery"][t]), 1.0),
                    (int(blocks["direct_export"][t]), 1.0),
                ),
                import_capacity,
            )

    @staticmethod
    def _add_flexible_energy_constraints(
        data: pd.DataFrame,
        dt: float,
        blocks: dict[str, np.ndarray],
        constraints: _ConstraintBuilder,
    ) -> None:
        dates = pd.to_datetime(data["timestamp"]).dt.date
        specifications = (
            ("irrigation_flexible", "irrigation_load_mw", "load.irrigation.flexible_share"),
            ("processing_flexible", "grain_processing_load_mw", "load.processing.flexible_share"),
            ("storage_flexible", "storage_cold_chain_load_mw", "load.storage.flexible_share"),
        )
        for _, positions in pd.Series(np.arange(len(data))).groupby(dates).groups.items():
            indices = np.asarray(list(positions), dtype=int)
            for block, column, share_code in specifications:
                share = phase1_parameter_value(share_code)
                required_energy = float(data[column].to_numpy(dtype=float)[indices].sum() * share * dt)
                constraints.equality(
                    ((int(blocks[block][position]), dt) for position in indices),
                    required_energy,
                )

    def _build_result(
        self,
        data: pd.DataFrame,
        dt: float,
        solution: np.ndarray,
        objective: np.ndarray,
        global_index: dict[str, int],
        blocks: dict[str, np.ndarray],
        fixed_direct_annual: float,
        request: AgriOptimizationRequest,
    ) -> AgriOptimizationResult:
        dispatch = data.copy()
        for name, indices in blocks.items():
            dispatch[f"{name}_mw"] = solution[indices]
        shares = {
            "irrigation": phase1_parameter_value("load.irrigation.flexible_share"),
            "processing": phase1_parameter_value("load.processing.flexible_share"),
            "storage": phase1_parameter_value("load.storage.flexible_share"),
        }
        dispatch["optimized_irrigation_load_mw"] = (
            (1.0 - shares["irrigation"]) * dispatch["irrigation_load_mw"] + dispatch["irrigation_flexible_mw"]
        )
        dispatch["optimized_processing_load_mw"] = (
            (1.0 - shares["processing"]) * dispatch["grain_processing_load_mw"]
            + dispatch["processing_flexible_mw"]
        )
        dispatch["optimized_storage_load_mw"] = (
            (1.0 - shares["storage"]) * dispatch["storage_cold_chain_load_mw"]
            + dispatch["storage_flexible_mw"]
        )
        dispatch["optimized_total_load_mw"] = (
            dispatch["optimized_irrigation_load_mw"]
            + dispatch["optimized_processing_load_mw"]
            + dispatch["optimized_storage_load_mw"]
            + dispatch["public_auxiliary_load_mw"]
        )
        capacities = {
            "pv_capacity_mw": float(solution[global_index["pv_capacity"]]),
            "green_direct_capacity_mw": float(solution[global_index["direct_capacity"]]),
            "battery_power_mw": float(solution[global_index["battery_power"]]),
            "battery_energy_mwh": float(solution[global_index["battery_energy"]]),
            "grid_peak_mw": float(solution[global_index["grid_peak"]]),
        }
        dispatch["pv_generation_mw"] = capacities["pv_capacity_mw"] * dispatch["pv_availability_pu"]
        direct_reference = phase1_parameter_value("green_direct.max_capacity_mw")
        direct_cf = np.clip(dispatch["direct_green_available_mw"] / direct_reference, 0.0, 1.0)
        dispatch["direct_green_injected_mw"] = capacities["green_direct_capacity_mw"] * direct_cf
        direct_loss = phase1_parameter_value("green_direct.base_loss_rate")
        dispatch["direct_green_line_loss_mw"] = dispatch["direct_green_injected_mw"] * direct_loss
        dispatch["direct_green_delivered_mw"] = dispatch["direct_green_injected_mw"] - dispatch[
            "direct_green_line_loss_mw"
        ]
        dispatch["battery_charge_total_mw"] = dispatch["pv_to_battery_mw"] + dispatch[
            "direct_to_battery_mw"
        ]
        dispatch["battery_discharge_total_mw"] = dispatch["battery_discharge_pv_mw"] + dispatch[
            "battery_discharge_direct_mw"
        ]
        dispatch["battery_soc_pv_mwh"] = dispatch["soc_pv_mw"]
        dispatch["battery_soc_direct_mwh"] = dispatch["soc_direct_mw"]
        dispatch["battery_soc_total_mwh"] = dispatch["battery_soc_pv_mwh"] + dispatch[
            "battery_soc_direct_mwh"
        ]
        dispatch["physical_green_to_load_mw"] = (
            dispatch["pv_to_load_mw"]
            + dispatch["direct_to_load_mw"]
            + dispatch["battery_discharge_total_mw"]
        )
        dispatch["carbon_emission_rate_tco2_per_hour"] = (
            dispatch["grid_to_load_mw"] * dispatch["grid_emission_factor_tco2_per_mwh"]
        )
        dispatch["bus_balance_error_mw"] = (
            dispatch["pv_generation_mw"]
            + dispatch["direct_green_delivered_mw"]
            + dispatch["grid_to_load_mw"]
            + dispatch["battery_discharge_total_mw"]
            - dispatch["optimized_total_load_mw"]
            - dispatch["battery_charge_total_mw"]
            - dispatch["pv_export_mw"]
            - dispatch["direct_export_mw"]
            - dispatch["pv_curtailment_mw"]
            - dispatch["direct_curtailment_mw"]
        )
        annual_demand = float(dispatch["optimized_total_load_mw"].sum() * dt)
        physical_green = float(dispatch["physical_green_to_load_mw"].sum() * dt)
        emissions = float(dispatch["carbon_emission_rate_tco2_per_hour"].sum() * dt)
        variable_objective = float(np.dot(objective, solution))
        annual_total_cost = variable_objective + fixed_direct_annual
        cost_breakdown = self._cost_breakdown(dispatch, capacities, dt, fixed_direct_annual)
        daily_task_error = self._maximum_daily_task_energy_error(dispatch, dt)
        summary = {
            "annual_demand_mwh": annual_demand,
            "annual_grid_import_mwh": float(dispatch["grid_to_load_mw"].sum() * dt),
            "annual_physical_green_to_load_mwh": physical_green,
            "physical_green_match_rate_percent": 100.0 * physical_green / max(annual_demand, 1e-9),
            "annual_carbon_emissions_tco2": emissions,
            "annual_total_cost_cny": annual_total_cost,
            "average_supply_cost_cny_per_mwh": annual_total_cost / max(annual_demand, 1e-9),
            "annual_pv_generation_mwh": float(dispatch["pv_generation_mw"].sum() * dt),
            "annual_direct_green_injected_mwh": float(dispatch["direct_green_injected_mw"].sum() * dt),
            "annual_direct_green_line_loss_mwh": float(dispatch["direct_green_line_loss_mw"].sum() * dt),
            "annual_export_mwh": float((dispatch["pv_export_mw"] + dispatch["direct_export_mw"]).sum() * dt),
            "annual_curtailment_mwh": float(
                (dispatch["pv_curtailment_mw"] + dispatch["direct_curtailment_mw"]).sum() * dt
            ),
            "annual_battery_charge_mwh": float(dispatch["battery_charge_total_mw"].sum() * dt),
            "annual_battery_discharge_mwh": float(dispatch["battery_discharge_total_mw"].sum() * dt),
            "max_bus_balance_error_mw": float(dispatch["bus_balance_error_mw"].abs().max()),
            "max_daily_production_task_energy_error_mwh": daily_task_error,
            "simultaneous_charge_discharge_hours": float(
                ((dispatch["battery_charge_total_mw"] > 1e-7) & (dispatch["battery_discharge_total_mw"] > 1e-7)).sum()
            ),
            "simultaneous_grid_import_export_hours": float(
                (
                    (dispatch["grid_to_load_mw"] > 1e-7)
                    & ((dispatch["pv_export_mw"] + dispatch["direct_export_mw"]) > 1e-7)
                ).sum()
            ),
            "target_physical_green_share_percent": 100.0 * request.target_physical_green_share,
        }
        strategy_name = "零碳协同优化" if request.target_physical_green_share >= 1.0 - 1e-9 else "低碳经济优化"
        return AgriOptimizationResult(True, "最优解", strategy_name, capacities, summary, cost_breakdown, dispatch)

    @staticmethod
    def _maximum_daily_task_energy_error(dispatch: pd.DataFrame, dt: float) -> float:
        dates = pd.to_datetime(dispatch["timestamp"]).dt.date
        pairs = (
            ("irrigation_load_mw", "optimized_irrigation_load_mw"),
            ("grain_processing_load_mw", "optimized_processing_load_mw"),
            ("storage_cold_chain_load_mw", "optimized_storage_load_mw"),
        )
        maximum = 0.0
        for baseline, optimized in pairs:
            daily_error = ((dispatch[optimized] - dispatch[baseline]) * dt).groupby(dates).sum().abs()
            maximum = max(maximum, float(daily_error.max()))
        return maximum

    def _cost_breakdown(
        self,
        dispatch: pd.DataFrame,
        capacities: dict[str, float],
        dt: float,
        fixed_direct_annual: float,
    ) -> dict[str, float]:
        annualization = self._capital_recovery_factor()
        fixed_om = phase1_parameter_value("finance.fixed_om_rate")
        pv_fixed = capacities["pv_capacity_mw"] * phase1_parameter_value("pv.capex_cny_per_mw") * (
            annualization + fixed_om
        )
        battery_fixed = (
            capacities["battery_power_mw"] * phase1_parameter_value("battery.capex_power_cny_per_mw")
            + capacities["battery_energy_mwh"] * phase1_parameter_value("battery.capex_energy_cny_per_mwh")
        ) * (annualization + fixed_om)
        grid_energy = float(
            (dispatch["grid_to_load_mw"] * dispatch["grid_buy_price_cny_per_mwh"]).sum() * dt
        )
        grid_demand = capacities["grid_peak_mw"] * phase1_parameter_value(
            "grid.agri_demand_charge_cny_per_mw_year"
        )
        direct_energy = float(dispatch["direct_green_injected_mw"].sum() * dt) * phase1_parameter_value(
            "green_direct.base_lcoe_cny_per_mwh"
        )
        carbon = float(dispatch["carbon_emission_rate_tco2_per_hour"].sum() * dt) * phase1_parameter_value(
            "carbon.price_cny_per_tco2"
        )
        degradation = float(dispatch["battery_discharge_total_mw"].sum() * dt) * phase1_parameter_value(
            "battery.degradation_cny_per_mwh"
        )
        curtailment = float(
            (dispatch["pv_curtailment_mw"] + dispatch["direct_curtailment_mw"]).sum() * dt
        ) * phase1_parameter_value("pv.curtailment_penalty_cny_per_mwh")
        export_revenue = float(
            (
                (dispatch["pv_export_mw"] + dispatch["direct_export_mw"])
                * np.maximum(
                    dispatch["grid_sell_price_cny_per_mwh"]
                    - phase1_parameter_value("grid.export_wheeling_cny_per_mwh"),
                    0.0,
                )
            ).sum()
            * dt
        )
        return {
            "光伏年化投资运维/元": pv_fixed,
            "储能年化投资运维/元": battery_fixed,
            "直连固定工程年化/元": fixed_direct_annual,
            "直连绿电购电/元": direct_energy,
            "公共电网电量费/元": grid_energy,
            "公共电网需量费/元": grid_demand,
            "碳成本/元": carbon,
            "储能衰减成本/元": degradation,
            "弃电惩罚/元": curtailment,
            "外送收益/元": -export_revenue,
        }

    @staticmethod
    def _failure_result(status: str) -> AgriOptimizationResult:
        return AgriOptimizationResult(False, status, "不可行", {}, {}, {}, pd.DataFrame())
