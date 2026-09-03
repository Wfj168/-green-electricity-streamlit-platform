from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from typing import Any

import pandas as pd

from src.application.agri_energy_flow_service import AgriEnergyFlowService
from src.application.agri_strategy_service import AgriStrategyService
from src.application.agri_stress_test_service import AgriReferenceCapacities, AgriStressTestService
from src.application.green_direct_benefit_service import GreenDirectBenefitService
from src.application.forecast_service import ForecastService
from src.core.agri_parameter_registry import (
    PHASE1_PARAMETER_REGISTRY,
    formal_readiness_gaps,
    phase1_parameter_value,
)
from src.model.agri_park_profiles import (
    PROFILE_SOURCE,
    PROFILE_VERSION,
    generate_agri_park_profiles,
    summarize_agri_park_profiles,
)
from src.version import PLATFORM_VERSION


V2_MODEL_VERSION = "agri-park-fusion-v2.1"
V2_PARAMETER_VERSION = "phase1-parameter-registry-v1"


def _frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", force_ascii=False, date_format="iso"))


def _float(value: Any) -> float:
    return float(value)


@lru_cache(maxsize=6)
def _cached_overview(year: int, resolution_minutes: int) -> dict[str, Any]:
    profiles = generate_agri_park_profiles(year=year, resolution_minutes=resolution_minutes)
    flow = AgriEnergyFlowService().simulate(profiles)
    dispatch = flow.dispatch
    representative_index = int(dispatch["total_meter_load_mw"].idxmax())
    representative = dispatch.loc[representative_index]
    timestamp = pd.Timestamp(representative["timestamp"])
    day_mask = pd.to_datetime(dispatch["timestamp"]).dt.date == timestamp.date()
    day = dispatch.loc[day_mask].copy()
    load_summary = summarize_agri_park_profiles(profiles)
    demand = _float(representative["total_meter_load_mw"])
    physical_green = _float(representative["physical_green_to_load_mw"])
    carbon_rate = _float(representative["carbon_emission_rate_tco2_per_hour"])
    soc_total = _float(representative["battery_soc_total_mwh"])
    battery_capacity = phase1_parameter_value("battery.demo_energy_mwh")
    # 展示百分比只由调度结果计算；容量为零时不制造百分比。
    soc_percent = 100.0 * soc_total / max(battery_capacity, 1e-9) if battery_capacity > 0 else 0.0
    green_share = 100.0 * physical_green / max(demand, 1e-9)

    load_mapping = (
        ("灌溉负荷", "irrigation_load_mw"),
        ("加工与烘干", "grain_processing_load_mw"),
        ("仓储冷链", "storage_cold_chain_load_mw"),
        ("公共辅助", "public_auxiliary_load_mw"),
    )
    loads = [
        {
            "code": column,
            "name": name,
            "powerMw": _float(representative[column]),
            "sharePercent": 100.0 * _float(representative[column]) / max(demand, 1e-9),
            "taskProgressPercent": None,
            "taskStatus": "尚未接入生产任务实绩",
        }
        for name, column in load_mapping
    ]
    trend = [
        {
            "timestamp": pd.Timestamp(row["timestamp"]).isoformat(),
            "loadMw": _float(row["total_meter_load_mw"]),
            "pvMw": _float(row["pv_generation_mw"]),
            "directDeliveredMw": _float(row["direct_green_delivered_mw"]),
            "gridMw": _float(row["grid_to_load_mw"]),
            "storageChargeMw": _float(row["battery_charge_total_mw"]),
            "storageDischargeMw": _float(row["battery_discharge_total_mw"]),
            "physicalGreenMw": _float(row["physical_green_to_load_mw"]),
        }
        for _, row in day.iterrows()
    ]
    return {
        "meta": {
            "parkId": "phase1-demo-agri-park",
            "parkName": "零碳农业示范园区",
            "asOf": timestamp.isoformat(),
            "dataStatus": "演示",
            "sourceIds": [PROFILE_VERSION, V2_PARAMETER_VERSION],
            "sourceReference": PROFILE_SOURCE,
            "qualityCode": "synthetic-traceable",
            "runId": f"energy-flow-{year}-{resolution_minutes}m",
            "modelVersion": V2_MODEL_VERSION,
            "platformVersion": PLATFORM_VERSION,
            "parameterVersion": V2_PARAMETER_VERSION,
            "currency": "CNY",
            "formalReadinessGapCount": len(formal_readiness_gaps()),
        },
        "metrics": {
            "totalLoadMw": demand,
            "pvPowerMw": _float(representative["pv_generation_mw"]),
            "directInjectedMw": _float(representative["direct_green_injected_mw"]),
            "directDeliveredMw": _float(representative["direct_green_delivered_mw"]),
            "directLineLossMw": _float(representative["direct_green_line_loss_mw"]),
            "storagePowerMw": _float(representative["battery_discharge_total_mw"])
            - _float(representative["battery_charge_total_mw"]),
            "storageSocPercent": soc_percent,
            "physicalGreenSharePercent": green_share,
            "carbonRateTco2PerHour": carbon_rate,
            "gridImportMw": _float(representative["grid_to_load_mw"]),
            "exportMw": _float(representative["pv_export_mw"])
            + _float(representative["direct_green_export_mw"]),
            "curtailmentMw": _float(representative["pv_curtailment_mw"])
            + _float(representative["direct_green_curtailment_mw"]),
            "busBalanceErrorMw": _float(representative["bus_balance_error_mw"]),
        },
        "loads": loads,
        "trend": trend,
        "annualSummary": {key: _float(value) for key, value in flow.summary.items()},
        "loadSummary": _frame_records(load_summary),
        "annualFlows": _frame_records(flow.annual_flows),
    }


@lru_cache(maxsize=3)
def _cached_strategies(year: int) -> dict[str, Any]:
    profiles = generate_agri_park_profiles(year=year, resolution_minutes=60)
    result = AgriStrategyService().compare(profiles)
    dispatch = result.zero_carbon.dispatch
    peak_index = int(dispatch["optimized_total_load_mw"].idxmax())
    peak_date = pd.Timestamp(dispatch.loc[peak_index, "timestamp"]).date()
    day = dispatch.loc[pd.to_datetime(dispatch["timestamp"]).dt.date == peak_date]
    day_ahead_plan = [
        {
            "timestamp": pd.Timestamp(row["timestamp"]).isoformat(),
            "totalLoadMw": _float(row["optimized_total_load_mw"]),
            "irrigationMw": _float(row["optimized_irrigation_load_mw"]),
            "processingMw": _float(row["optimized_processing_load_mw"]),
            "coldStorageMw": _float(row["optimized_storage_load_mw"]),
            "auxiliaryMw": _float(row["public_auxiliary_load_mw"]),
            "pvMw": _float(row["pv_generation_mw"]),
            "directDeliveredMw": _float(row["direct_green_delivered_mw"]),
            "storageChargeMw": _float(row["battery_charge_total_mw"]),
            "storageDischargeMw": _float(row["battery_discharge_total_mw"]),
            "storageSocMwh": _float(row["battery_soc_total_mwh"]),
            "gridMw": _float(row["grid_to_load_mw"]),
            "exportMw": _float(row["pv_export_mw"]) + _float(row["direct_export_mw"]),
            "curtailmentMw": _float(row["pv_curtailment_mw"])
            + _float(row["direct_curtailment_mw"]),
            "balanceErrorMw": _float(row["bus_balance_error_mw"]),
        }
        for _, row in day.iterrows()
    ]
    return {
        "meta": {
            "dataStatus": "演示",
            "sourceReference": PROFILE_SOURCE,
            "modelVersion": V2_MODEL_VERSION,
            "parameterVersion": V2_PARAMETER_VERSION,
            "currency": "CNY",
        },
        "strategies": _frame_records(result.comparison),
        "recommendedCapacities": {
            key: _float(value) for key, value in result.zero_carbon.capacities.items()
        },
        "recommendedSummary": {
            key: _float(value) for key, value in result.zero_carbon.summary.items()
        },
        "recommendedCostBreakdown": {
            key: _float(value) for key, value in result.zero_carbon.cost_breakdown.items()
        },
        "dayAheadPlan": day_ahead_plan,
    }


@lru_cache(maxsize=2)
def _cached_stress_tests(year: int) -> dict[str, Any]:
    strategies = _cached_strategies(year)
    capacities = strategies["recommendedCapacities"]
    profiles = generate_agri_park_profiles(year=year, resolution_minutes=60)
    result = AgriStressTestService().evaluate(
        profiles,
        AgriReferenceCapacities(
            pv_capacity_mw=capacities["pv_capacity_mw"],
            green_direct_capacity_mw=capacities["green_direct_capacity_mw"],
            battery_power_mw=capacities["battery_power_mw"],
            battery_energy_mwh=capacities["battery_energy_mwh"],
        ),
    )
    return {
        "meta": {
            "dataStatus": "演示",
            "sourceReference": PROFILE_SOURCE,
            "modelVersion": V2_MODEL_VERSION,
            "parameterVersion": V2_PARAMETER_VERSION,
            "currency": "CNY",
        },
        "stressTests": _frame_records(result.table),
    }


@lru_cache(maxsize=3)
def _cached_green_direct_benefits(year: int) -> dict[str, Any]:
    profiles = generate_agri_park_profiles(year=year, resolution_minutes=60)
    result = GreenDirectBenefitService().evaluate(profiles)
    return {
        "meta": {
            "dataStatus": "演示",
            "sourceReference": PROFILE_SOURCE,
            "modelVersion": V2_MODEL_VERSION,
            "parameterVersion": V2_PARAMETER_VERSION,
            "currency": "CNY",
        },
        "schemes": _frame_records(result.schemes),
        "attribution": _frame_records(result.attribution),
        "contractTerms": result.contract_terms,
        "methodology": result.methodology,
    }


@lru_cache(maxsize=3)
def _cached_forecast_center(year: int) -> dict[str, Any]:
    profiles = generate_agri_park_profiles(year=year, resolution_minutes=15)
    data = profiles.copy()
    data["pv_generation_mw"] = (
        data["pv_availability_pu"]
        * phase1_parameter_value("pv.demo_installed_capacity_mw")
    )
    service = ForecastService()
    definitions = (
        ("load", "园区总负荷", "total_meter_load_mw", "兆瓦"),
        ("pv", "园区光伏出力", "pv_generation_mw", "兆瓦"),
        ("direct", "直连可用功率", "direct_green_available_mw", "兆瓦"),
        ("weather", "环境温度", "ambient_temperature_c", "摄氏度"),
        ("price", "公共电网购电价格", "grid_buy_price_cny_per_mwh", "元/兆瓦时"),
        ("task", "粮食加工任务负荷", "grain_processing_load_mw", "兆瓦"),
    )
    series: list[dict[str, Any]] = []
    for code, name, target, unit in definitions:
        evaluation = service.evaluate_baselines(data, target=target)
        forecast = service.day_ahead(data, evaluation)
        value_column = f"forecast_{target}"
        series.append(
            {
                "code": code,
                "name": name,
                "unit": unit,
                "versionId": forecast.version_id,
                "modelName": forecast.model_name,
                "trainingStart": evaluation.training_start,
                "trainingEnd": evaluation.training_end,
                "validationStart": evaluation.validation_start,
                "validationEnd": evaluation.validation_end,
                "evaluation": _frame_records(evaluation.metrics),
                "values": [
                    {
                        "timestamp": pd.Timestamp(row["timestamp"]).isoformat(),
                        "value": _float(row[value_column]),
                    }
                    for _, row in forecast.data.iterrows()
                ],
            }
        )
    return {
        "meta": {
            "dataStatus": "演示",
            "sourceReference": PROFILE_SOURCE,
            "modelVersion": "seasonal-baseline-v1",
            "parameterVersion": V2_PARAMETER_VERSION,
            "currency": "CNY",
            "intervalMinutes": 15,
            "horizonPoints": 96,
        },
        "series": series,
    }


@lru_cache(maxsize=1)
def _cached_asset_register() -> dict[str, Any]:
    """生成第一阶段应建资产与计量台账，不将演示配置冒充现场资产。"""

    energy_assets = [
        {"assetCode": "NY-PV-001", "assetName": "园区光伏系统", "assetType": "本地光伏", "ratedPower": phase1_parameter_value("pv.demo_installed_capacity_mw"), "powerUnit": "兆瓦", "ratedEnergy": None, "energyUnit": "--", "status": "演示配置，待现场核验"},
        {"assetCode": "NY-GD-001", "assetName": "绿电直连通道", "assetType": "绿电直连", "ratedPower": phase1_parameter_value("green_direct.demo_contract_capacity_mw"), "powerUnit": "兆瓦", "ratedEnergy": None, "energyUnit": "--", "status": "演示合同，待合同核验"},
        {"assetCode": "NY-ES-001", "assetName": "电化学储能系统", "assetType": "储能", "ratedPower": phase1_parameter_value("battery.demo_power_mw"), "powerUnit": "兆瓦", "ratedEnergy": phase1_parameter_value("battery.demo_energy_mwh"), "energyUnit": "兆瓦时", "status": "演示配置，待铭牌核验"},
        {"assetCode": "NY-TR-001", "assetName": "园区主变压器", "assetType": "配电设备", "ratedPower": phase1_parameter_value("grid.transformer_capacity_mva"), "powerUnit": "兆伏安", "ratedEnergy": None, "energyUnit": "--", "status": "演示配置，待接入批复核验"},
    ]
    agricultural_assets = [
        {"assetCode": "AG-IR-001", "assetName": "灌溉泵组", "assetType": "灌溉", "ratedPower": phase1_parameter_value("load.irrigation.peak_mw"), "powerUnit": "兆瓦", "critical": "季节性关键", "status": "负荷等值，待设备拆分"},
        {"assetCode": "AG-PR-001", "assetName": "粮食加工与烘干线", "assetType": "加工", "ratedPower": phase1_parameter_value("load.processing.peak_mw"), "powerUnit": "兆瓦", "critical": "生产关键", "status": "负荷等值，待设备拆分"},
        {"assetCode": "AG-CS-001", "assetName": "仓储冷链系统", "assetType": "冷链", "ratedPower": phase1_parameter_value("load.storage.peak_mw"), "powerUnit": "兆瓦", "critical": "连续关键", "status": "负荷等值，待设备拆分"},
        {"assetCode": "AG-AU-001", "assetName": "公共辅助系统", "assetType": "辅助", "ratedPower": phase1_parameter_value("load.auxiliary.peak_mw"), "powerUnit": "兆瓦", "critical": "一般", "status": "负荷等值，待设备拆分"},
    ]
    meter_names = [
        ("MT-GW-001", "园区关口总表", "双向", "园区交流母线"),
        ("MT-PV-001", "光伏出口表", "正向", "园区光伏系统"),
        ("MT-GD-001", "直连受端表", "正向", "绿电直连通道"),
        ("MT-ES-001", "储能双向表", "双向", "电化学储能系统"),
        ("MT-IR-001", "灌溉分表", "正向", "灌溉泵组"),
        ("MT-PR-001", "加工分表", "正向", "粮食加工与烘干线"),
        ("MT-CS-001", "冷链分表", "正向", "仓储冷链系统"),
        ("MT-AU-001", "辅助分表", "正向", "公共辅助系统"),
    ]
    meters = [
        {"meterCode": code, "meterName": name, "direction": direction, "objectName": object_name, "interval": "15分钟", "unit": "千瓦时", "qualityStatus": "待接入"}
        for code, name, direction, object_name in meter_names
    ]
    topology = [
        {"from": "园区光伏系统", "to": "园区交流母线", "relation": "本地发电"},
        {"from": "绿电直连通道", "to": "园区交流母线", "relation": "线损后送达"},
        {"from": "公共电网", "to": "园区交流母线", "relation": "补充购电"},
        {"from": "电化学储能系统", "to": "园区交流母线", "relation": "双向充放电"},
        {"from": "园区交流母线", "to": "四类农业负荷", "relation": "分项供电"},
    ]
    return {
        "meta": {
            "dataStatus": "待现场核验",
            "sourceReference": "第一阶段农业园区演示基准与待采集模板",
            "modelVersion": V2_MODEL_VERSION,
            "parameterVersion": V2_PARAMETER_VERSION,
            "currency": "CNY",
        },
        "energyAssets": energy_assets,
        "agriculturalAssets": agricultural_assets,
        "meters": meters,
        "topology": topology,
    }


class V2ModelFacade:
    """为融合版页面提供稳定、可追溯、纯 JSON 的模型服务边界。"""

    def overview(self, *, year: int = 2025, resolution_minutes: int = 60) -> dict[str, Any]:
        if not 2020 <= year <= 2100:
            raise ValueError("年份必须在2020至2100之间")
        if resolution_minutes not in {15, 30, 60}:
            raise ValueError("时间分辨率只支持15、30或60分钟")
        return deepcopy(_cached_overview(year, resolution_minutes))

    def parameters(self) -> dict[str, Any]:
        return {
            "meta": {
                "dataStatus": "演示参数与正式资料缺口并存",
                "sourceReference": "第一阶段参数台账；每项参数均记录来源等级、来源凭证与设置方法",
                "modelVersion": "本页不使用计算模型",
                "parameterVersion": V2_PARAMETER_VERSION,
                "count": len(PHASE1_PARAMETER_REGISTRY),
                "formalReadinessGapCount": len(formal_readiness_gaps()),
                "currency": "CNY",
            },
            "parameters": [parameter.to_payload() for parameter in PHASE1_PARAMETER_REGISTRY],
        }

    def strategies(self, *, year: int = 2025) -> dict[str, Any]:
        if not 2020 <= year <= 2100:
            raise ValueError("年份必须在2020至2100之间")
        return deepcopy(_cached_strategies(year))

    def stress_tests(self, *, year: int = 2025) -> dict[str, Any]:
        if not 2020 <= year <= 2100:
            raise ValueError("年份必须在2020至2100之间")
        return deepcopy(_cached_stress_tests(year))

    def green_direct_benefits(self, *, year: int = 2025) -> dict[str, Any]:
        if not 2020 <= year <= 2100:
            raise ValueError("年份必须在2020至2100之间")
        return deepcopy(_cached_green_direct_benefits(year))

    def asset_register(self) -> dict[str, Any]:
        return deepcopy(_cached_asset_register())

    def forecast_center(self, *, year: int = 2025) -> dict[str, Any]:
        if not 2020 <= year <= 2100:
            raise ValueError("年份必须在2020至2100之间")
        return deepcopy(_cached_forecast_center(year))
