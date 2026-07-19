from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class GreenDirectRequest:
    annual_demand_mwh: float
    annual_green_mwh: float
    target_share: float
    planning_years: int
    park_lcoe_cny_per_mwh: float
    vpp_lcoe_cny_per_mwh: float
    base_lcoe_cny_per_mwh: float
    park_loss_rate: float = 0.015
    vpp_loss_rate: float = 0.025
    base_loss_rate: float = 0.035
    park_fixed_cost_wan_cny: float = 600.0
    vpp_fixed_cost_wan_cny: float = 900.0
    base_fixed_cost_wan_cny: float = 1800.0


@dataclass(frozen=True, slots=True)
class GreenDirectResult:
    annual_target_green_mwh: float
    annual_green_gap_mwh: float
    options: pd.DataFrame
    recommended_mode: str
    recommended_cost_wan_cny: float


class GreenDirectService:
    MODES = (
        ("园区内新增绿电", "park"),
        ("虚拟电厂聚合绿电", "vpp"),
        ("绿电基地直连", "base"),
    )

    def evaluate(self, request: GreenDirectRequest) -> GreenDirectResult:
        self._validate(request)
        target = request.annual_demand_mwh * request.target_share
        gap = max(0.0, target - request.annual_green_mwh)
        rows = []
        for display_name, prefix in self.MODES:
            loss = float(getattr(request, f"{prefix}_loss_rate"))
            delivered_energy = gap / max(1.0 - loss, 1e-9)
            lcoe = float(getattr(request, f"{prefix}_lcoe_cny_per_mwh"))
            fixed_cost = float(getattr(request, f"{prefix}_fixed_cost_wan_cny"))
            total_cost = delivered_energy * lcoe * request.planning_years / 10_000.0 + fixed_cost
            rows.append(
                {
                    "方案": display_name,
                    "需采购电量/MWh每年": delivered_energy,
                    "线路或聚合损耗/%": loss * 100.0,
                    "规划期成本/万元": total_cost,
                }
            )
        options = pd.DataFrame(rows)
        best = options.loc[options["规划期成本/万元"].idxmin()]
        return GreenDirectResult(target, gap, options, str(best["方案"]), float(best["规划期成本/万元"]))

    @staticmethod
    def from_v17_metrics(metrics: dict[str, Any]) -> pd.DataFrame:
        mapping = {
            "园区内新增绿电": "Park-internal green-direct cost",
            "虚拟电厂聚合绿电": "VPP aggregated green-direct cost",
            "绿电基地直连": "Remote green-base direct cost",
        }
        rows = []
        for mode, metric in mapping.items():
            value = metrics.get(metric)
            if value is not None:
                rows.append({"方案": mode, "年度成本/万元": float(value) * 100.0})
        return pd.DataFrame(rows)

    @staticmethod
    def _validate(request: GreenDirectRequest) -> None:
        if request.annual_demand_mwh < 0 or request.annual_green_mwh < 0:
            raise ValueError("年度用电量和绿电量不能小于0")
        if not 0 <= request.target_share <= 1:
            raise ValueError("目标绿电占比必须在0至100%之间")
        if request.planning_years <= 0:
            raise ValueError("规划周期必须大于0")
        for name in (
            "park_lcoe_cny_per_mwh",
            "vpp_lcoe_cny_per_mwh",
            "base_lcoe_cny_per_mwh",
            "park_fixed_cost_wan_cny",
            "vpp_fixed_cost_wan_cny",
            "base_fixed_cost_wan_cny",
        ):
            if getattr(request, name) < 0:
                raise ValueError(f"{name}不能小于0")
        for name in ("park_loss_rate", "vpp_loss_rate", "base_loss_rate"):
            value = getattr(request, name)
            if not 0 <= value < 1:
                raise ValueError(f"{name}必须在0至100%之间")
