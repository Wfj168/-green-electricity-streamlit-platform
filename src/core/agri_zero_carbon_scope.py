from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Final


SCOPE_ID: Final = "agri-zero-carbon-park-phase1"
SCOPE_VERSION: Final = "1.0.0"


class ZeroCarbonStatus(str, Enum):
    ACHIEVED = "零碳达标"
    NOT_ACHIEVED = "零碳未达标"
    NOT_VERIFIABLE = "暂不可核验"


@dataclass(frozen=True, slots=True)
class LoadCategory:
    code: str
    name: str
    included_objects: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ZeroCarbonAssessment:
    status: ZeroCarbonStatus
    reason: str


@dataclass(frozen=True, slots=True)
class AgriParkScopeContract:
    scope_id: str
    version: str
    title: str
    accounting_boundary: str
    planning_resolution: str
    dispatch_resolution: str
    load_categories: tuple[LoadCategory, ...]
    electricity_sources: tuple[str, ...]
    included_emission_sources: tuple[str, ...]
    excluded_phase1_items: tuple[str, ...]
    comparison_strategies: tuple[str, ...]
    stress_tests: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


PHASE1_SCOPE: Final = AgriParkScopeContract(
    scope_id=SCOPE_ID,
    version=SCOPE_VERSION,
    title="基于绿电直连的零碳农业园区源网荷储优化调度",
    accounting_boundary="农业园区生产运营阶段的能源相关直接排放与购入能源间接排放",
    planning_resolution="连续8760小时年度规划",
    dispatch_resolution="15分钟日前与滚动调度",
    load_categories=(
        LoadCategory(
            code="irrigation_pumping",
            name="灌溉与水泵负荷",
            included_objects=("春灌泵站", "排涝泵站", "园区供水与水肥设备"),
        ),
        LoadCategory(
            code="grain_processing",
            name="粮食烘干与加工负荷",
            included_objects=("清选输送", "粮食烘干", "碾米加工", "包装生产"),
        ),
        LoadCategory(
            code="storage_cold_chain",
            name="仓储与冷链负荷",
            included_objects=("原粮仓储", "成品仓储", "种子库", "冷库与保鲜设施"),
        ),
        LoadCategory(
            code="public_auxiliary",
            name="公共与辅助负荷",
            included_objects=("办公照明", "通风除湿", "污水处理", "消防安防与其他辅助设备"),
        ),
    ),
    electricity_sources=(
        "园区本地光伏",
        "外部绿电基地物理直连",
        "可核验聚合或合同绿电",
        "公共电网普通购电",
        "按来源分账的储能放电",
    ),
    included_emission_sources=(
        "公共电网普通购电产生的间接排放",
        "园区内燃气、燃油和其他化石燃料的直接排放",
        "外购热力或其他购入能源产生的间接排放",
        "储能、变换和直连线路损耗引起的增量能源排放",
    ),
    excluded_phase1_items=(
        "化肥、农药、种子和土壤过程排放",
        "畜禽肠道发酵和粪污过程排放",
        "园区外农业运输和物流排放",
        "建筑、设备和基础设施隐含碳",
        "土地利用变化和碳汇核算",
        "碳抵消量用于宣称零碳",
        "低空经济、绿氢和电转其他能源",
        "县域居民与普通商业负荷",
    ),
    comparison_strategies=(
        "现状基准方案",
        "绿电直连方案",
        "零碳源网荷储协同方案",
    ),
    stress_tests=(
        "低光伏出力年",
        "春灌负荷增长",
        "农产品集中加工",
        "绿电直连受限",
        "电价与设备投资波动",
        "公共电网短时限电",
    ),
)


def assess_zero_carbon_status(
    residual_emissions_tco2: float | None,
    *,
    energy_balance_valid: bool,
    parameter_provenance_complete: bool,
    unverified_offset_tco2: float = 0.0,
    tolerance_tco2: float = 0.01,
) -> ZeroCarbonAssessment:
    """Apply the phase-one zero-carbon claim gate.

    Carbon offsets are reported separately and cannot be used to turn positive
    operational emissions into a zero-carbon result in phase one.
    """

    if residual_emissions_tco2 is None:
        return ZeroCarbonAssessment(ZeroCarbonStatus.NOT_VERIFIABLE, "缺少剩余运营排放结果")
    if not energy_balance_valid:
        return ZeroCarbonAssessment(ZeroCarbonStatus.NOT_VERIFIABLE, "能量平衡校验未通过")
    if not parameter_provenance_complete:
        return ZeroCarbonAssessment(ZeroCarbonStatus.NOT_VERIFIABLE, "关键参数来源不完整")
    if unverified_offset_tco2 > tolerance_tco2:
        return ZeroCarbonAssessment(ZeroCarbonStatus.NOT_VERIFIABLE, "使用了第一阶段不认可的碳抵消量")
    if residual_emissions_tco2 <= tolerance_tco2:
        return ZeroCarbonAssessment(ZeroCarbonStatus.ACHIEVED, "能源运营边界内剩余排放不超过核算容差")
    return ZeroCarbonAssessment(ZeroCarbonStatus.NOT_ACHIEVED, "能源运营边界内仍存在剩余排放")
