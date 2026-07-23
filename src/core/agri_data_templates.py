from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class TemplateColumn:
    name: str
    chinese_name: str
    unit: str
    required: bool
    source_requirement: str
    description: str


TIMESERIES_COLUMNS: Final[tuple[TemplateColumn, ...]] = (
    TemplateColumn("timestamp", "时间戳", "北京时间", True, "计量系统", "连续15分钟时间戳，不允许重复"),
    TemplateColumn("irrigation_load_mw", "灌溉与水泵负荷", "兆瓦", True, "分项电表或设备计算", "非负有功功率"),
    TemplateColumn("grain_processing_load_mw", "粮食烘干与加工负荷", "兆瓦", True, "分项电表或设备计算", "非负有功功率"),
    TemplateColumn("storage_cold_chain_load_mw", "仓储与冷链负荷", "兆瓦", True, "分项电表或设备计算", "非负有功功率"),
    TemplateColumn("public_auxiliary_load_mw", "公共与辅助负荷", "兆瓦", True, "分项电表或总表残差", "非负有功功率"),
    TemplateColumn("total_meter_load_mw", "园区总表负荷", "兆瓦", True, "园区关口总表", "用于与四类分项负荷闭环"),
    TemplateColumn("pv_availability_pu", "光伏单位容量可用出力", "标幺值", True, "气象与光伏实测", "范围0至1"),
    TemplateColumn("direct_green_available_mw", "绿电直连可用功率", "兆瓦", True, "绿电基地与专线计划", "专线损耗前可用功率"),
    TemplateColumn("grid_buy_price_cny_per_mwh", "购电价格", "元/兆瓦时", True, "供电合同或正式电价", "含分时电价"),
    TemplateColumn("grid_sell_price_cny_per_mwh", "售电价格", "元/兆瓦时", True, "购售电合同", "无售电时填0"),
    TemplateColumn("grid_emission_factor_tco2_per_mwh", "电网排放因子", "吨二氧化碳/兆瓦时", True, "官方因子及版本", "可使用逐时或统一因子"),
    TemplateColumn("ambient_temperature_c", "环境温度", "摄氏度", False, "气象站", "用于冷链和热泵负荷"),
    TemplateColumn("solar_irradiance_w_per_m2", "太阳辐照度", "瓦/平方米", False, "气象站", "用于光伏校准"),
    TemplateColumn("data_quality_flag", "数据质量标记", "文本", True, "数据处理记录", "实测、插补、缺失或异常"),
    TemplateColumn("source_reference", "数据来源", "文本", True, "文件或接口标识", "记录表号、接口、文件和版本"),
)


ASSET_COLUMNS: Final[tuple[TemplateColumn, ...]] = (
    TemplateColumn("asset_id", "设备编号", "文本", True, "资产台账", "园区内唯一编号"),
    TemplateColumn("asset_name", "设备名称", "文本", True, "资产台账", "中文名称"),
    TemplateColumn("asset_type", "设备类型", "文本", True, "资产台账", "光伏、储能、泵、烘干机、冷库、变压器等"),
    TemplateColumn("load_category", "所属负荷类别", "文本", True, "边界基线", "四类农业负荷或能源设备"),
    TemplateColumn("rated_power_mw", "额定功率", "兆瓦", True, "设备铭牌", "非负"),
    TemplateColumn("rated_energy_mwh", "额定容量", "兆瓦时", False, "设备铭牌", "储能设备填写"),
    TemplateColumn("efficiency_or_cop", "效率或性能系数", "无量纲", False, "铭牌或测试", "注明采用效率还是性能系数"),
    TemplateColumn("minimum_power_mw", "最小运行功率", "兆瓦", False, "设备说明书", "设备启用时的下限"),
    TemplateColumn("ramp_mw_per_15min", "15分钟爬坡能力", "兆瓦/15分钟", False, "设备说明书", "用于滚动调度"),
    TemplateColumn("critical_load", "是否关键负荷", "布尔值", True, "生产和安全要求", "是或否"),
    TemplateColumn("source_reference", "参数来源", "文本", True, "文件编号", "铭牌照片、合同、报价或计算书"),
)


PRODUCTION_TASK_COLUMNS: Final[tuple[TemplateColumn, ...]] = (
    TemplateColumn("task_id", "任务编号", "文本", True, "生产计划", "园区内唯一编号"),
    TemplateColumn("load_category", "负荷类别", "文本", True, "边界基线", "灌溉、加工、仓储冷链或公共辅助"),
    TemplateColumn("asset_id", "执行设备编号", "文本", True, "资产台账", "与设备模板关联"),
    TemplateColumn("earliest_start", "最早开始时间", "北京时间", True, "生产计划", "任务可开始时刻"),
    TemplateColumn("latest_finish", "最晚完成时间", "北京时间", True, "生产计划", "任务交付边界"),
    TemplateColumn("duration_intervals", "持续时间", "15分钟间隔数", True, "工艺计算", "连续运行间隔数"),
    TemplateColumn("minimum_power_mw", "最小功率", "兆瓦", True, "设备与工艺", "任务运行功率下限"),
    TemplateColumn("maximum_power_mw", "最大功率", "兆瓦", True, "设备与工艺", "任务运行功率上限"),
    TemplateColumn("required_energy_mwh", "任务所需电量", "兆瓦时", True, "工艺计算", "与功率和持续时间一致"),
    TemplateColumn("product_quantity_t", "对应产品数量", "吨", False, "生产计划", "用于单位产品能耗和碳强度"),
    TemplateColumn("must_run", "是否必须完成", "布尔值", True, "生产要求", "关键任务不得削减"),
    TemplateColumn("source_reference", "任务来源", "文本", True, "计划编号", "记录生产计划或计算依据"),
)


SOURCE_LEDGER_COLUMNS: Final[tuple[TemplateColumn, ...]] = (
    TemplateColumn("source_id", "来源编号", "文本", True, "项目资料目录", "唯一编号"),
    TemplateColumn("source_grade", "来源等级", "文本", True, "参数治理规则", "A至E"),
    TemplateColumn("document_name", "资料名称", "文本", True, "原始资料", "合同、账单、铭牌、通知或计算书"),
    TemplateColumn("document_version", "资料版本", "文本", True, "原始资料", "发布日期或版本号"),
    TemplateColumn("effective_date", "生效日期", "日期", False, "原始资料", "参数适用日期"),
    TemplateColumn("owner", "资料责任方", "文本", True, "项目管理", "提供或审批资料的责任方"),
    TemplateColumn("storage_location", "存储位置", "文本", True, "项目资料目录", "文件路径、网址或接口"),
    TemplateColumn("verification_status", "核验状态", "文本", True, "项目审核", "已核验、待补充或演示参数"),
    TemplateColumn("notes", "说明", "文本", False, "项目审核", "适用范围和处理方法"),
)


def required_column_names(columns: tuple[TemplateColumn, ...]) -> tuple[str, ...]:
    return tuple(column.name for column in columns if column.required)


def validate_template_headers(headers: list[str], columns: tuple[TemplateColumn, ...]) -> list[str]:
    normalized = {header.strip() for header in headers}
    return [name for name in required_column_names(columns) if name not in normalized]
