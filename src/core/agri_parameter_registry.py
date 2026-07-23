from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Final


class ParameterSourceGrade(str, Enum):
    A = "A-计量实测"
    B = "B-合同铭牌报价"
    C = "C-政府与官方"
    D = "D-工程计算"
    E = "E-演示假设"


class ParameterVerificationStatus(str, Enum):
    VERIFIED = "已核验"
    PENDING = "待补充"
    DEMO = "演示参数"


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    code: str
    name: str
    group: str
    unit: str
    value: float | None
    minimum: float | None
    maximum: float | None
    source_grade: ParameterSourceGrade
    verification_status: ParameterVerificationStatus
    source_reference: str
    setting_method: str
    formal_required: bool = True

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["source_grade"] = self.source_grade.value
        payload["verification_status"] = self.verification_status.value
        return payload


LEGACY_DEMO_REFERENCE: Final = "现有V17 0.8.0演示基线（2025口径）；正式项目必须以属地资料替换"
BOUNDARY_REFERENCE: Final = "docs/phase1_agri_zero_carbon_scope.md"
METER_PENDING_REFERENCE: Final = "待接入园区总表、分表或能源管理系统15分钟实测数据"
CONTRACT_PENDING_REFERENCE: Final = "待接入园区供电合同、绿电合同、接入批复或设备报价"
ENGINEERING_PENDING_REFERENCE: Final = "待根据设备铭牌、生产工艺和工程计算书核定"
AGRI_DEMO_REFERENCE: Final = "第一阶段农业园区演示基准v1；按农业生产设备尺度构造，非实测数据"


def _demo(
    code: str,
    name: str,
    group: str,
    unit: str,
    value: float,
    minimum: float | None,
    maximum: float | None,
    setting_method: str,
    source_reference: str = LEGACY_DEMO_REFERENCE,
) -> ParameterDefinition:
    return ParameterDefinition(
        code,
        name,
        group,
        unit,
        value,
        minimum,
        maximum,
        ParameterSourceGrade.E,
        ParameterVerificationStatus.DEMO,
        source_reference,
        setting_method,
    )


def _required(
    code: str,
    name: str,
    group: str,
    unit: str,
    minimum: float | None,
    maximum: float | None,
    source_grade: ParameterSourceGrade,
    source_reference: str,
    setting_method: str,
) -> ParameterDefinition:
    return ParameterDefinition(
        code,
        name,
        group,
        unit,
        None,
        minimum,
        maximum,
        source_grade,
        ParameterVerificationStatus.PENDING,
        source_reference,
        setting_method,
    )


PHASE1_PARAMETER_REGISTRY: Final[tuple[ParameterDefinition, ...]] = (
    _demo("finance.planning_years", "规划周期", "经济与碳", "年", 20.0, 1.0, 50.0, "沿用现有V17演示规划周期"),
    _demo("finance.discount_rate", "折现率", "经济与碳", "比例", 0.05, 0.0, 0.30, "沿用现有V17演示财务口径"),
    _demo("finance.fixed_om_rate", "固定运维费率", "经济与碳", "比例/年", 0.02, 0.0, 0.20, "按初始投资比例估算"),
    _demo("carbon.price_cny_per_tco2", "碳价", "经济与碳", "元/吨二氧化碳", 215.0, 0.0, 5000.0, "沿用现有V17演示值"),
    ParameterDefinition(
        "carbon.zero_tolerance_tco2",
        "零碳判定容差",
        "经济与碳",
        "吨二氧化碳/年",
        0.01,
        0.0,
        1.0,
        ParameterSourceGrade.D,
        ParameterVerificationStatus.VERIFIED,
        BOUNDARY_REFERENCE,
        "仅作为数值计算容差，不作为允许排放配额",
    ),
    ParameterDefinition(
        "green.total_target_share",
        "园区运营绿电目标比例",
        "经济与碳",
        "比例",
        1.0,
        0.0,
        1.0,
        ParameterSourceGrade.D,
        ParameterVerificationStatus.VERIFIED,
        BOUNDARY_REFERENCE,
        "零碳运营目标要求全部用电具有可核验绿电或零排放来源",
    ),
    _demo("grid.import_capacity_mw", "公共电网进口容量", "电网接口", "兆瓦", 120.0, 0.0, 1000.0, "现有县域搜索边界"),
    _demo("grid.export_capacity_mw", "公共电网出口容量", "电网接口", "兆瓦", 5.0, 0.0, 1000.0, "现有县域搜索边界"),
    _demo("grid.demand_charge_cny_per_mw_year", "最大需量费用", "电网接口", "元/兆瓦·年", 18000.0, 0.0, None, "现有V17演示值"),
    _demo("grid.export_capacity_charge_cny_per_mw_year", "外送容量费用", "电网接口", "元/兆瓦·年", 6000.0, 0.0, None, "现有V17演示值"),
    _demo("grid.export_wheeling_cny_per_mwh", "外送过网费用", "电网接口", "元/兆瓦时", 8.0, 0.0, None, "现有V17演示值"),
    _demo("grid.emission_factor_tco2_per_mwh", "公共电网排放因子", "电网接口", "吨二氧化碳/兆瓦时", 0.55, 0.0, 2.0, "固定演示因子"),
    _demo("grid.reserve_margin", "规划备用率", "电网接口", "比例", 0.10, 0.0, 1.0, "现有V17充裕度假设"),
    _demo("grid.max_unserved_energy_ratio", "最大供电不足比例", "电网接口", "比例", 0.0001, 0.0, 1.0, "现有可靠性筛查值"),
    _demo("grid.transformer_capacity_mva", "园区变压器容量", "电网接口", "兆伏安", 5.0, 0.0, None, "演示园区采用5兆伏安接入边界", AGRI_DEMO_REFERENCE),
    _demo("grid.power_factor", "园区功率因数", "电网接口", "比例", 0.90, 0.0, 1.0, "演示园区按0.90折算有功容量", AGRI_DEMO_REFERENCE),
    _demo("pv.max_capacity_mw", "光伏规划容量上限", "本地光伏", "兆瓦", 220.0, 0.0, 1000.0, "现有县域搜索边界"),
    _demo("pv.capex_cny_per_mw", "光伏单位投资", "本地光伏", "元/兆瓦", 3_200_000.0, 0.0, None, "现有V17演示造价"),
    _demo("pv.capacity_credit", "光伏容量可信度", "本地光伏", "比例", 0.08, 0.0, 1.0, "现有V17充裕度假设"),
    _demo("pv.curtailment_penalty_cny_per_mwh", "弃光惩罚", "本地光伏", "元/兆瓦时", 20.0, 0.0, None, "现有V17优化惩罚"),
    _required("pv.usable_area_m2", "可用光伏面积", "本地光伏", "平方米", 0.0, None, ParameterSourceGrade.B, CONTRACT_PENDING_REFERENCE, "依据屋顶和土地测绘资料"),
    _required("pv.capacity_density_mw_per_m2", "光伏单位面积容量", "本地光伏", "兆瓦/平方米", 0.0, 0.01, ParameterSourceGrade.D, ENGINEERING_PENDING_REFERENCE, "由组件、排布、遮挡和消防间距计算"),
    _demo("battery.max_power_mw", "储能功率上限", "电化学储能", "兆瓦", 120.0, 0.0, 1000.0, "现有县域搜索边界"),
    _demo("battery.max_energy_mwh", "储能容量上限", "电化学储能", "兆瓦时", 300.0, 0.0, 5000.0, "现有县域搜索边界"),
    _demo("battery.capex_power_cny_per_mw", "储能功率投资", "电化学储能", "元/兆瓦", 700_000.0, 0.0, None, "现有V17演示造价"),
    _demo("battery.capex_energy_cny_per_mwh", "储能能量投资", "电化学储能", "元/兆瓦时", 900_000.0, 0.0, None, "现有V17演示造价"),
    _demo("battery.charge_efficiency", "储能充电效率", "电化学储能", "比例", 0.95, 0.0, 1.0, "现有V17技术假设"),
    _demo("battery.discharge_efficiency", "储能放电效率", "电化学储能", "比例", 0.95, 0.0, 1.0, "现有V17技术假设"),
    _demo("battery.soc_min", "储能最小荷电状态", "电化学储能", "比例", 0.10, 0.0, 1.0, "现有V17技术假设"),
    _demo("battery.soc_max", "储能最大荷电状态", "电化学储能", "比例", 0.90, 0.0, 1.0, "现有V17技术假设"),
    _demo("battery.soc_initial", "储能初始荷电状态", "电化学储能", "比例", 0.50, 0.0, 1.0, "现有V17技术假设"),
    _demo("battery.self_discharge_per_hour", "储能小时自放电率", "电化学储能", "比例/小时", 0.0002, 0.0, 0.10, "现有V17技术假设"),
    _demo("battery.degradation_cny_per_mwh", "储能衰减成本", "电化学储能", "元/兆瓦时吞吐", 120.0, 0.0, None, "现有V17演示值"),
    _demo("battery.max_equivalent_cycles", "储能年等效循环上限", "电化学储能", "次/年", 350.0, 0.0, 1000.0, "现有V17寿命筛查值"),
    _demo("green_direct.max_capacity_mw", "绿电直连通道容量", "绿电直连", "兆瓦", 5.0, 0.0, None, "演示通道容量与园区变压器尺度一致", AGRI_DEMO_REFERENCE),
    _demo("green_direct.park_lcoe_cny_per_mwh", "园区内新增绿电成本", "绿电直连", "元/兆瓦时", 320.0, 0.0, None, "统一采用V17演示基线"),
    _demo("green_direct.vpp_lcoe_cny_per_mwh", "聚合绿电成本", "绿电直连", "元/兆瓦时", 395.0, 0.0, None, "统一采用V17演示基线"),
    _demo("green_direct.base_lcoe_cny_per_mwh", "外部绿电基地成本", "绿电直连", "元/兆瓦时", 355.0, 0.0, None, "统一采用V17演示基线"),
    _demo("green_direct.park_loss_rate", "园区内绿电损耗率", "绿电直连", "比例", 0.015, 0.0, 1.0, "现有V17演示值"),
    _demo("green_direct.vpp_loss_rate", "聚合绿电损耗率", "绿电直连", "比例", 0.025, 0.0, 1.0, "现有V17演示值"),
    _demo("green_direct.base_loss_rate", "外部专线损耗率", "绿电直连", "比例", 0.035, 0.0, 1.0, "现有V17演示值"),
    _demo("green_direct.park_fixed_cost_cny", "园区内绿电固定工程费", "绿电直连", "元", 6_000_000.0, 0.0, None, "现有V17演示值"),
    _demo("green_direct.vpp_fixed_cost_cny", "聚合平台固定费", "绿电直连", "元", 9_000_000.0, 0.0, None, "现有V17演示值"),
    _demo("green_direct.base_fixed_cost_cny", "外部绿电专线固定费", "绿电直连", "元", 18_000_000.0, 0.0, None, "现有V17演示值"),
    _demo("load.irrigation.annual_energy_mwh", "灌溉年用电量", "农业负荷", "兆瓦时/年", 521.93, 0.0, None, "4月20日至6月10日，上午1.20兆瓦、下午0.90兆瓦并按周因子积分", AGRI_DEMO_REFERENCE),
    _demo("load.irrigation.peak_mw", "灌溉峰值负荷", "农业负荷", "兆瓦", 1.20, 0.0, None, "演示设置为4台300千瓦泵组同时运行", AGRI_DEMO_REFERENCE),
    _demo("load.irrigation.flexible_share", "灌溉可转移比例", "农业负荷", "比例", 0.28, 0.0, 1.0, "沿用现有灌溉柔性代理比例"),
    _demo("load.processing.annual_energy_mwh", "粮食加工年用电量", "农业负荷", "兆瓦时/年", 3825.83, 0.0, None, "按常规生产和9月15日至11月30日秋收班次积分", AGRI_DEMO_REFERENCE),
    _demo("load.processing.peak_mw", "粮食加工峰值负荷", "农业负荷", "兆瓦", 2.00, 0.0, None, "参考2兆瓦级农业加工用电规模设置", AGRI_DEMO_REFERENCE),
    _demo("load.processing.flexible_share", "粮食加工可转移比例", "农业负荷", "比例", 0.18, 0.0, 1.0, "沿用现有加工柔性代理比例"),
    _demo("load.storage.annual_energy_mwh", "仓储冷链年用电量", "农业负荷", "兆瓦时/年", 3287.88, 0.0, None, "按基础仓储、温度、日间作业和秋收增量积分", AGRI_DEMO_REFERENCE),
    _demo("load.storage.peak_mw", "仓储冷链峰值负荷", "农业负荷", "兆瓦", 0.537, 0.0, None, "由温度和秋收叠加曲线形成的15分钟峰值", AGRI_DEMO_REFERENCE),
    _demo("load.storage.flexible_share", "仓储冷链可转移比例", "农业负荷", "比例", 0.12, 0.0, 1.0, "沿用现有冷库柔性代理比例"),
    _demo("load.auxiliary.annual_energy_mwh", "公共辅助年用电量", "农业负荷", "兆瓦时/年", 1266.72, 0.0, None, "按基础、工作时段、秋收和冬季增量积分", AGRI_DEMO_REFERENCE),
    _demo("load.auxiliary.peak_mw", "公共辅助峰值负荷", "农业负荷", "兆瓦", 0.24, 0.0, None, "演示公共辅助容量上限", AGRI_DEMO_REFERENCE),
    _demo("load.auxiliary.flexible_share", "公共辅助可转移比例", "农业负荷", "比例", 0.05, 0.0, 1.0, "沿用现有居民辅助柔性代理比例"),
    _demo("thermal.heat_pump_cop", "热泵性能系数", "电气化供热制冷", "无量纲", 3.2, 1.0, 8.0, "现有V17技术假设"),
    _demo("thermal.refrigeration_cop", "制冷性能系数", "电气化供热制冷", "无量纲", 3.0, 1.0, 10.0, "现有V17技术假设"),
    _demo("thermal.heat_pump_capex_cny_per_mw", "热泵单位投资", "电气化供热制冷", "元/兆瓦", 1_200_000.0, 0.0, None, "现有V17演示造价"),
    _demo("thermal.refrigeration_capex_cny_per_mw", "电制冷单位投资", "电气化供热制冷", "元/兆瓦", 900_000.0, 0.0, None, "现有V17演示造价"),
)


_PARAMETER_BY_CODE: Final = {parameter.code: parameter for parameter in PHASE1_PARAMETER_REGISTRY}


def phase1_parameter(code: str) -> ParameterDefinition:
    try:
        return _PARAMETER_BY_CODE[code]
    except KeyError as exc:
        raise KeyError(f"未知的第一阶段参数：{code}") from exc


def phase1_parameter_value(code: str) -> float:
    parameter = phase1_parameter(code)
    if parameter.value is None:
        raise ValueError(f"第一阶段参数尚未赋值：{code}")
    return float(parameter.value)


def validate_phase1_parameter_registry() -> list[str]:
    issues: list[str] = []
    codes = [parameter.code for parameter in PHASE1_PARAMETER_REGISTRY]
    if len(codes) != len(set(codes)):
        issues.append("参数代码存在重复")
    for parameter in PHASE1_PARAMETER_REGISTRY:
        if not parameter.source_reference.strip():
            issues.append(f"{parameter.code}缺少来源")
        if not parameter.setting_method.strip():
            issues.append(f"{parameter.code}缺少设置方法")
        if parameter.value is not None:
            if parameter.minimum is not None and parameter.value < parameter.minimum:
                issues.append(f"{parameter.code}小于允许下限")
            if parameter.maximum is not None and parameter.value > parameter.maximum:
                issues.append(f"{parameter.code}超过允许上限")
    return issues


def formal_readiness_gaps() -> list[str]:
    return [
        parameter.code
        for parameter in PHASE1_PARAMETER_REGISTRY
        if parameter.formal_required
        and (
            parameter.value is None
            or parameter.source_grade is ParameterSourceGrade.E
            or parameter.verification_status is not ParameterVerificationStatus.VERIFIED
        )
    ]
