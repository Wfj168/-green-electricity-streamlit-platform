from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class AuditSeverity(str, Enum):
    BLOCKER = "阻断"
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


class AuditStatus(str, Enum):
    OPEN = "待整改"
    ACCEPTED = "已接受"
    RESOLVED = "已解决"


@dataclass(frozen=True, slots=True)
class AuditFinding:
    finding_id: str
    category: str
    severity: AuditSeverity
    title: str
    evidence: str
    impact: str
    remediation_step: int
    status: AuditStatus = AuditStatus.OPEN

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["severity"] = self.severity.value
        payload["status"] = self.status.value
        return payload


CURRENT_STATE_FINDINGS: tuple[AuditFinding, ...] = (
    AuditFinding(
        "DATA-001",
        "数据与负荷",
        AuditSeverity.BLOCKER,
        "当前负荷是县域特征化合成数据",
        "六类典型日由固定函数和随机平滑噪声生成，代码明确标注为非实测数据。",
        "不能直接作为农业园区的正式负荷、容量和收益结论。",
        3,
    ),
    AuditFinding(
        "DATA-002",
        "数据与负荷",
        AuditSeverity.HIGH,
        "第一阶段边界外负荷仍进入总负荷",
        "居民、商业、一般工业和低空经济负荷仍与农业负荷相加。",
        "农业园区指标分母、容量规模和能源流向均被边界外对象稀释。",
        4,
    ),
    AuditFinding(
        "TIME-001",
        "时间序列",
        AuditSeverity.BLOCKER,
        "典型日加权替代连续全年",
        "当前使用六类典型日加权为365天，储能在每个典型日内循环闭合。",
        "无法表达连续阴天、跨日荷电状态和真实农业季节持续性。",
        4,
    ),
    AuditFinding(
        "PARAM-001",
        "参数治理",
        AuditSeverity.BLOCKER,
        "关键参数没有逐项来源台账",
        "价格、造价、碳因子、设备效率和容量边界分散在模型、配置和页面中。",
        "结果不能逐参数解释，也难以在正式项目中替换和审批。",
        3,
        AuditStatus.RESOLVED,
    ),
    AuditFinding(
        "PARAM-002",
        "参数治理",
        AuditSeverity.HIGH,
        "绿电直连存在两套默认度电成本",
        "V17为320/395/355元每兆瓦时，快速页面为360/430/390元每兆瓦时。",
        "同一项目可能因入口不同得到不同的方案推荐。",
        3,
        AuditStatus.RESOLVED,
    ),
    AuditFinding(
        "SCOPE-001",
        "模型边界",
        AuditSeverity.HIGH,
        "县域技术集合与农业园区专项不一致",
        "风电、热电联产、燃气锅炉、绿氢、电转其他能源和低空经济仍在默认模型范围内。",
        "增加无关参数和图表，降低第一阶段结论的可解释性。",
        4,
    ),
    AuditFinding(
        "GREEN-001",
        "绿电直连",
        AuditSeverity.BLOCKER,
        "绿电直连没有进入逐时物理平衡",
        "当前仅根据年度目标电量、度电成本、损耗和固定费进行事后方案比较。",
        "无法说明绿电在什么时刻到达、供给哪类负荷、是否进入储能。",
        5,
        AuditStatus.RESOLVED,
    ),
    AuditFinding(
        "GREEN-002",
        "绿电直连",
        AuditSeverity.BLOCKER,
        "储能没有按电量来源分账",
        "只有统一荷电状态，没有本地光伏、直连绿电和普通电网充电来源。",
        "储能放电可能被错误计入绿电覆盖，无法形成可核验能量流。",
        5,
        AuditStatus.RESOLVED,
    ),
    AuditFinding(
        "CARBON-001",
        "碳核算",
        AuditSeverity.BLOCKER,
        "碳核算与绿电物理流未联动",
        "电网排放采用固定0.55吨每兆瓦时，绿电直连没有替代逐时电网购电。",
        "零碳状态不能由当前结果可靠判定。",
        5,
        AuditStatus.RESOLVED,
    ),
    AuditFinding(
        "MODEL-001",
        "优化模型",
        AuditSeverity.HIGH,
        "规划模式未强制储能充放电互斥",
        "默认strict_storage_exclusivity为False。",
        "成本参数异常或退化时可能出现同一时段充放电。",
        6,
        AuditStatus.RESOLVED,
    ),
    AuditFinding(
        "MODEL-002",
        "优化模型",
        AuditSeverity.HIGH,
        "规划模式未强制电网购售电互斥",
        "默认strict_grid_exchange_exclusivity为False。",
        "在价格和补贴边界变化时可能出现同一时段购售电。",
        6,
        AuditStatus.RESOLVED,
    ),
    AuditFinding(
        "MODEL-003",
        "优化模型",
        AuditSeverity.HIGH,
        "园区农业生产任务未形成约束",
        "加工、灌溉和仓储目前主要是固定负荷曲线或比例柔性代理。",
        "模型可能降低成本但不能证明生产任务、产量和品质要求得到满足。",
        6,
        AuditStatus.RESOLVED,
    ),
    AuditFinding(
        "CHART-001",
        "结果图",
        AuditSeverity.BLOCKER,
        "年度桑基图缺少绿电直连、损耗和分项农业负荷",
        "图中只有光伏、风电、电网、热电联产、储能与统一终端负荷。",
        "无法解释零碳农业园区的真实能量流向。",
        7,
    ),
    AuditFinding(
        "CHART-002",
        "结果图",
        AuditSeverity.HIGH,
        "雷达图混合多个口径并强化理想化视觉",
        "五个百分比指标经过0至100裁剪后直接绘制，缺少目标值和绝对量。",
        "容易把相近或受分母影响的指标解释为全面优秀。",
        7,
    ),
    AuditFinding(
        "CHART-003",
        "结果图",
        AuditSeverity.HIGH,
        "热力图和持续时间曲线不是真实连续全年",
        "热力图只有六类典型日，持续时间曲线通过复制权重构造。",
        "不能识别连续极端事件和真实月度农业季节。",
        7,
    ),
    AuditFinding(
        "CHART-004",
        "结果图",
        AuditSeverity.MEDIUM,
        "综合得分依赖当前场景集合的相对归一化",
        "场景集合变化时0至100分会变化，权重尚未由农业园区项目方确认。",
        "得分不能作为绝对项目可研结论。",
        7,
    ),
    AuditFinding(
        "UI-001",
        "页面与表达",
        AuditSeverity.MEDIUM,
        "页面仍保留县域和工业园区叙事",
        "页面标题、场景名称和说明仍大量出现县域、工业园区、低空与绿氢。",
        "与第一阶段农业零碳园区定位不一致。",
        9,
    ),
)


def current_state_audit_summary() -> dict[str, object]:
    severity_counts = {
        severity.value: sum(finding.severity is severity for finding in CURRENT_STATE_FINDINGS)
        for severity in AuditSeverity
    }
    return {
        "finding_count": len(CURRENT_STATE_FINDINGS),
        "open_count": sum(finding.status is AuditStatus.OPEN for finding in CURRENT_STATE_FINDINGS),
        "severity_counts": severity_counts,
        "findings": [finding.to_payload() for finding in CURRENT_STATE_FINDINGS],
    }
