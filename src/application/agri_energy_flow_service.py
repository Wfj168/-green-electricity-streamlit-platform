from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.core.agri_parameter_registry import phase1_parameter_value
from src.model.agri_park_profiles import validate_agri_park_profiles


LOAD_COLUMNS = {
    "灌溉与水泵": "irrigation_load_mw",
    "粮食烘干与加工": "grain_processing_load_mw",
    "仓储与冷链": "storage_cold_chain_load_mw",
    "公共与辅助": "public_auxiliary_load_mw",
}


@dataclass(frozen=True, slots=True)
class AgriEnergyFlowRequest:
    pv_capacity_mw: float = phase1_parameter_value("pv.demo_installed_capacity_mw")
    green_direct_capacity_mw: float = phase1_parameter_value("green_direct.demo_contract_capacity_mw")
    green_direct_reference_capacity_mw: float = phase1_parameter_value("green_direct.max_capacity_mw")
    green_direct_line_loss_rate: float = phase1_parameter_value("green_direct.base_loss_rate")
    battery_power_mw: float = phase1_parameter_value("battery.demo_power_mw")
    battery_energy_mwh: float = phase1_parameter_value("battery.demo_energy_mwh")
    battery_charge_efficiency: float = phase1_parameter_value("battery.charge_efficiency")
    battery_discharge_efficiency: float = phase1_parameter_value("battery.discharge_efficiency")
    battery_soc_min: float = phase1_parameter_value("battery.soc_min")
    battery_soc_max: float = phase1_parameter_value("battery.soc_max")
    battery_initial_soc: float = phase1_parameter_value("battery.soc_min")
    export_capacity_mw: float = phase1_parameter_value("grid.demo_export_capacity_mw")


@dataclass(frozen=True, slots=True)
class AgriEnergyFlowResult:
    dispatch: pd.DataFrame
    annual_flows: pd.DataFrame
    summary: dict[str, float]


class AgriEnergyFlowService:
    def simulate(
        self,
        profiles: pd.DataFrame,
        request: AgriEnergyFlowRequest | None = None,
    ) -> AgriEnergyFlowResult:
        request = request or AgriEnergyFlowRequest()
        self._validate_request(request)
        profile_issues = validate_agri_park_profiles(profiles)
        if profile_issues:
            raise ValueError("；".join(profile_issues))
        data = profiles.copy().reset_index(drop=True)
        timestamps = pd.to_datetime(data["timestamp"])
        dt = (
            float(timestamps.diff().dropna().dt.total_seconds().median()) / 3600.0
            if len(timestamps) > 1
            else float(data.get("resolution_minutes", pd.Series([60.0])).iloc[0]) / 60.0
        )

        output: dict[str, np.ndarray] = {
            name: np.zeros(len(data), dtype=float)
            for name in (
                "pv_generation_mw",
                "direct_green_injected_mw",
                "direct_green_line_loss_mw",
                "direct_green_delivered_mw",
                "pv_to_load_mw",
                "direct_green_to_load_mw",
                "battery_discharge_pv_origin_mw",
                "battery_discharge_direct_origin_mw",
                "battery_discharge_grid_origin_mw",
                "battery_discharge_total_mw",
                "grid_to_load_mw",
                "battery_charge_pv_origin_mw",
                "battery_charge_direct_origin_mw",
                "battery_charge_grid_origin_mw",
                "battery_charge_total_mw",
                "battery_charge_loss_mw",
                "battery_discharge_loss_mw",
                "battery_soc_pv_mwh",
                "battery_soc_direct_mwh",
                "battery_soc_grid_mwh",
                "battery_soc_total_mwh",
                "pv_export_mw",
                "direct_green_export_mw",
                "pv_curtailment_mw",
                "direct_green_curtailment_mw",
                "physical_green_to_load_mw",
                "carbon_emission_rate_tco2_per_hour",
                "bus_balance_error_mw",
                "system_balance_error_mw",
                "load_supply_allocation_error_mw",
            )
        }

        soc_by_origin = {
            "pv": 0.0,
            "direct": 0.0,
            "grid": request.battery_initial_soc * request.battery_energy_mwh,
        }
        minimum_soc_mwh = request.battery_soc_min * request.battery_energy_mwh
        maximum_soc_mwh = request.battery_soc_max * request.battery_energy_mwh

        for index, row in data.iterrows():
            load = float(row["total_meter_load_mw"])
            pv_generation = request.pv_capacity_mw * float(row["pv_availability_pu"])
            reference_available = float(row["direct_green_available_mw"])
            direct_cf = reference_available / max(request.green_direct_reference_capacity_mw, 1e-9)
            direct_injected = request.green_direct_capacity_mw * max(0.0, min(direct_cf, 1.0))
            direct_line_loss = direct_injected * request.green_direct_line_loss_rate
            direct_delivered = direct_injected - direct_line_loss

            remaining_load = load
            pv_to_load = min(pv_generation, remaining_load)
            remaining_load -= pv_to_load
            direct_to_load = min(direct_delivered, remaining_load)
            remaining_load -= direct_to_load
            pv_surplus = pv_generation - pv_to_load
            direct_surplus = direct_delivered - direct_to_load

            soc_before = sum(soc_by_origin.values())
            discharge_total = 0.0
            discharge_by_origin = {"pv": 0.0, "direct": 0.0, "grid": 0.0}
            if remaining_load > 1e-12 and request.battery_energy_mwh > 0.0:
                available_stored = max(soc_before - minimum_soc_mwh, 0.0)
                discharge_total = min(
                    remaining_load,
                    request.battery_power_mw,
                    available_stored * request.battery_discharge_efficiency / dt,
                )
                stored_withdrawal = discharge_total * dt / request.battery_discharge_efficiency
                if soc_before > 1e-12 and stored_withdrawal > 0.0:
                    for origin in soc_by_origin:
                        share = soc_by_origin[origin] / soc_before
                        withdrawal = min(soc_by_origin[origin], stored_withdrawal * share)
                        soc_by_origin[origin] -= withdrawal
                        discharge_by_origin[origin] = withdrawal * request.battery_discharge_efficiency / dt
                remaining_load -= discharge_total

            grid_to_load = max(remaining_load, 0.0)

            total_surplus = pv_surplus + direct_surplus
            charge_total = 0.0
            charge_by_origin = {"pv": 0.0, "direct": 0.0, "grid": 0.0}
            soc_after_discharge = sum(soc_by_origin.values())
            if total_surplus > 1e-12 and request.battery_energy_mwh > 0.0:
                charge_room_input = max(maximum_soc_mwh - soc_after_discharge, 0.0) / (
                    request.battery_charge_efficiency * dt
                )
                charge_total = min(total_surplus, request.battery_power_mw, charge_room_input)
                pv_share = pv_surplus / total_surplus
                charge_by_origin["pv"] = charge_total * pv_share
                charge_by_origin["direct"] = charge_total - charge_by_origin["pv"]
                soc_by_origin["pv"] += (
                    charge_by_origin["pv"] * request.battery_charge_efficiency * dt
                )
                soc_by_origin["direct"] += (
                    charge_by_origin["direct"] * request.battery_charge_efficiency * dt
                )
                pv_surplus -= charge_by_origin["pv"]
                direct_surplus -= charge_by_origin["direct"]

            remaining_surplus = max(pv_surplus + direct_surplus, 0.0)
            export_total = min(remaining_surplus, request.export_capacity_mw)
            if remaining_surplus > 1e-12:
                pv_export = export_total * pv_surplus / remaining_surplus
            else:
                pv_export = 0.0
            direct_export = export_total - pv_export
            pv_curtailment = max(pv_surplus - pv_export, 0.0)
            direct_curtailment = max(direct_surplus - direct_export, 0.0)

            soc_after = sum(soc_by_origin.values())
            charge_loss = charge_total * (1.0 - request.battery_charge_efficiency)
            discharge_loss = discharge_total * (
                1.0 / request.battery_discharge_efficiency - 1.0
            )
            soc_delta_rate = (soc_after - soc_before) / dt
            bus_balance_error = (
                pv_generation
                + direct_delivered
                + grid_to_load
                + discharge_total
                - load
                - charge_total
                - export_total
                - pv_curtailment
                - direct_curtailment
            )
            system_balance_error = (
                pv_generation
                + direct_injected
                + grid_to_load
                - load
                - export_total
                - pv_curtailment
                - direct_curtailment
                - direct_line_loss
                - charge_loss
                - discharge_loss
                - soc_delta_rate
            )
            supplied_load = (
                pv_to_load
                + direct_to_load
                + sum(discharge_by_origin.values())
                + grid_to_load
            )
            physical_green_to_load = (
                pv_to_load
                + direct_to_load
                + discharge_by_origin["pv"]
                + discharge_by_origin["direct"]
            )
            carbon_rate = (
                grid_to_load + discharge_by_origin["grid"]
            ) * float(row["grid_emission_factor_tco2_per_mwh"])

            values: dict[str, float] = {
                "pv_generation_mw": pv_generation,
                "direct_green_injected_mw": direct_injected,
                "direct_green_line_loss_mw": direct_line_loss,
                "direct_green_delivered_mw": direct_delivered,
                "pv_to_load_mw": pv_to_load,
                "direct_green_to_load_mw": direct_to_load,
                "battery_discharge_pv_origin_mw": discharge_by_origin["pv"],
                "battery_discharge_direct_origin_mw": discharge_by_origin["direct"],
                "battery_discharge_grid_origin_mw": discharge_by_origin["grid"],
                "battery_discharge_total_mw": discharge_total,
                "grid_to_load_mw": grid_to_load,
                "battery_charge_pv_origin_mw": charge_by_origin["pv"],
                "battery_charge_direct_origin_mw": charge_by_origin["direct"],
                "battery_charge_grid_origin_mw": charge_by_origin["grid"],
                "battery_charge_total_mw": charge_total,
                "battery_charge_loss_mw": charge_loss,
                "battery_discharge_loss_mw": discharge_loss,
                "battery_soc_pv_mwh": soc_by_origin["pv"],
                "battery_soc_direct_mwh": soc_by_origin["direct"],
                "battery_soc_grid_mwh": soc_by_origin["grid"],
                "battery_soc_total_mwh": soc_after,
                "pv_export_mw": pv_export,
                "direct_green_export_mw": direct_export,
                "pv_curtailment_mw": pv_curtailment,
                "direct_green_curtailment_mw": direct_curtailment,
                "physical_green_to_load_mw": physical_green_to_load,
                "carbon_emission_rate_tco2_per_hour": carbon_rate,
                "bus_balance_error_mw": bus_balance_error,
                "system_balance_error_mw": system_balance_error,
                "load_supply_allocation_error_mw": supplied_load - load,
            }
            for name, value in values.items():
                output[name][index] = value

        for name, values in output.items():
            data[name] = values
        annual_flows = self._annual_flow_table(data, dt)
        summary = self._summary(data, dt, request)
        return AgriEnergyFlowResult(data, annual_flows, summary)

    @staticmethod
    def _validate_request(request: AgriEnergyFlowRequest) -> None:
        nonnegative = {
            "光伏容量": request.pv_capacity_mw,
            "绿电直连容量": request.green_direct_capacity_mw,
            "绿电参考容量": request.green_direct_reference_capacity_mw,
            "储能功率": request.battery_power_mw,
            "储能容量": request.battery_energy_mwh,
            "外送容量": request.export_capacity_mw,
        }
        for name, value in nonnegative.items():
            if value < 0.0:
                raise ValueError(f"{name}不能小于0")
        ratios = {
            "直连损耗率": request.green_direct_line_loss_rate,
            "储能充电效率": request.battery_charge_efficiency,
            "储能放电效率": request.battery_discharge_efficiency,
            "储能最小荷电状态": request.battery_soc_min,
            "储能最大荷电状态": request.battery_soc_max,
            "储能初始荷电状态": request.battery_initial_soc,
        }
        for name, value in ratios.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name}必须在0至1之间")
        if request.green_direct_reference_capacity_mw <= 0.0:
            raise ValueError("绿电参考容量必须大于0")
        if request.battery_charge_efficiency <= 0.0 or request.battery_discharge_efficiency <= 0.0:
            raise ValueError("储能效率必须大于0")
        if not request.battery_soc_min <= request.battery_initial_soc <= request.battery_soc_max:
            raise ValueError("储能初始荷电状态必须位于允许范围内")

    @staticmethod
    def _annual_flow_table(dispatch: pd.DataFrame, dt: float) -> pd.DataFrame:
        source_columns = {
            "本地光伏直供": "pv_to_load_mw",
            "直连绿电直供": "direct_green_to_load_mw",
            "储能放电（光伏来源）": "battery_discharge_pv_origin_mw",
            "储能放电（直连来源）": "battery_discharge_direct_origin_mw",
            "储能放电（普通电来源）": "battery_discharge_grid_origin_mw",
            "公共电网当期购电": "grid_to_load_mw",
        }
        rows: list[dict[str, Any]] = []
        load = dispatch["total_meter_load_mw"].replace(0.0, np.nan)
        for source_name, source_column in source_columns.items():
            source_supply = dispatch[source_column]
            for load_name, load_column in LOAD_COLUMNS.items():
                allocated = source_supply * dispatch[load_column].div(load).fillna(0.0)
                value = float(allocated.sum() * dt)
                if value > 1e-9:
                    rows.append({"来源": source_name, "去向": load_name, "电量/兆瓦时": value, "类型": "负荷供能"})
        other_flows = (
            ("园区本地光伏", "电储能", "battery_charge_pv_origin_mw", "储能充电"),
            ("直连绿电", "电储能", "battery_charge_direct_origin_mw", "储能充电"),
            ("园区本地光伏", "公共电网外送", "pv_export_mw", "外送"),
            ("直连绿电", "公共电网外送", "direct_green_export_mw", "外送"),
            ("园区本地光伏", "弃光", "pv_curtailment_mw", "弃电"),
            ("直连绿电", "弃电", "direct_green_curtailment_mw", "弃电"),
            ("外部绿电基地", "直连线路损耗", "direct_green_line_loss_mw", "线路损耗"),
            ("电储能", "充电损耗", "battery_charge_loss_mw", "储能损耗"),
            ("电储能", "放电损耗", "battery_discharge_loss_mw", "储能损耗"),
        )
        for source, target, column, flow_type in other_flows:
            value = float(dispatch[column].sum() * dt)
            if value > 1e-9:
                rows.append({"来源": source, "去向": target, "电量/兆瓦时": value, "类型": flow_type})
        return pd.DataFrame(rows)

    @staticmethod
    def _summary(
        dispatch: pd.DataFrame,
        dt: float,
        request: AgriEnergyFlowRequest,
    ) -> dict[str, float]:
        annual_demand = float(dispatch["total_meter_load_mw"].sum() * dt)
        physical_green = float(dispatch["physical_green_to_load_mw"].sum() * dt)
        annual_pv = float(dispatch["pv_generation_mw"].sum() * dt)
        annual_direct_injected = float(dispatch["direct_green_injected_mw"].sum() * dt)
        annual_direct_delivered = float(dispatch["direct_green_delivered_mw"].sum() * dt)
        annual_grid = float(dispatch["grid_to_load_mw"].sum() * dt)
        annual_export = float((dispatch["pv_export_mw"] + dispatch["direct_green_export_mw"]).sum() * dt)
        annual_curtailment = float(
            (dispatch["pv_curtailment_mw"] + dispatch["direct_green_curtailment_mw"]).sum() * dt
        )
        annual_battery_charge = float(dispatch["battery_charge_total_mw"].sum() * dt)
        annual_battery_discharge = float(dispatch["battery_discharge_total_mw"].sum() * dt)
        annual_storage_loss = float(
            (dispatch["battery_charge_loss_mw"] + dispatch["battery_discharge_loss_mw"]).sum() * dt
        )
        return {
            "annual_demand_mwh": annual_demand,
            "annual_pv_generation_mwh": annual_pv,
            "annual_direct_green_injected_mwh": annual_direct_injected,
            "annual_direct_green_delivered_mwh": annual_direct_delivered,
            "annual_direct_green_line_loss_mwh": annual_direct_injected - annual_direct_delivered,
            "annual_grid_import_mwh": annual_grid,
            "annual_physical_green_to_load_mwh": physical_green,
            "physical_green_match_rate_percent": 100.0 * physical_green / max(annual_demand, 1e-9),
            "annual_export_mwh": annual_export,
            "annual_curtailment_mwh": annual_curtailment,
            "annual_battery_charge_mwh": annual_battery_charge,
            "annual_battery_discharge_mwh": annual_battery_discharge,
            "annual_storage_loss_mwh": annual_storage_loss,
            "battery_initial_soc_mwh": request.battery_initial_soc * request.battery_energy_mwh,
            "battery_final_soc_mwh": float(dispatch["battery_soc_total_mwh"].iloc[-1]),
            "annual_carbon_emissions_tco2": float(
                dispatch["carbon_emission_rate_tco2_per_hour"].sum() * dt
            ),
            "max_bus_balance_error_mw": float(dispatch["bus_balance_error_mw"].abs().max()),
            "max_system_balance_error_mw": float(dispatch["system_balance_error_mw"].abs().max()),
            "max_load_allocation_error_mw": float(dispatch["load_supply_allocation_error_mw"].abs().max()),
        }
