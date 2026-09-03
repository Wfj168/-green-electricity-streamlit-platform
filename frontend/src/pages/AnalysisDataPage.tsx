import { useCallback, type ReactNode } from "react";
import { ApartmentOutlined, AuditOutlined, CheckCircleOutlined, DatabaseOutlined, DollarOutlined, DownloadOutlined, SafetyCertificateOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Alert, Button, Descriptions, Skeleton, Table, Tag } from "antd";
import { ComparisonBars } from "../components/ComparisonBars";
import { MetricCard } from "../components/MetricCard";
import { Panel } from "../components/Panel";
import { useV2Resource } from "../hooks/useV2Resource";
import { v2Api, type AssetData, type GreenBenefitData, type OverviewData, type ParametersData, type StrategyData, type StressTestData } from "../services/api";
import type { NavPage } from "../types";
import { readSession } from "../services/session";

interface AnalysisDataPageProps { page: NavPage }
type Payload = OverviewData | StrategyData | GreenBenefitData | StressTestData | AssetData | ParametersData;
interface Metric { label: string; value: string; unit: string; tone?: "green" | "amber" | "red"; icon: ReactNode }
interface Bar { label: string; value: number; display: string; tone?: "cyan" | "green" | "amber" | "red" }

const FIELD_LABELS: Record<string, string> = {
  assetCode: "资产编码", assetName: "资产名称", assetType: "资产类型", ratedPower: "额定功率", powerUnit: "功率单位",
  ratedEnergy: "额定容量", energyUnit: "容量单位", status: "核验状态", critical: "重要等级",
  meterCode: "计量点编码", meterName: "计量点名称", direction: "计量方向", objectName: "计量对象", interval: "采集周期",
  unit: "单位", qualityStatus: "质量状态", from: "来源节点", to: "去向节点", relation: "关系",
  code: "参数编码", name: "参数名称", group: "参数分组", value: "当前值", minimum: "最小值", maximum: "最大值",
  source_grade: "来源等级", verification_status: "核验状态", source_reference: "来源凭证", setting_method: "设置方法", formal_required: "正式项目必填",
};

const ANNUAL_LABELS: Record<string, string> = {
  annual_demand_mwh: "园区年用电量/兆瓦时", annual_pv_generation_mwh: "本地光伏年发电量/兆瓦时",
  annual_direct_green_injected_mwh: "直连送端年注入/兆瓦时", annual_direct_green_delivered_mwh: "直连受端年送达/兆瓦时",
  annual_direct_green_line_loss_mwh: "直连线路年损耗/兆瓦时", annual_grid_import_mwh: "公共电网年购电量/兆瓦时",
  annual_physical_green_to_load_mwh: "物理绿电年供负荷/兆瓦时", physical_green_match_rate_percent: "物理绿电匹配率/%",
  annual_export_mwh: "年上网电量/兆瓦时", annual_curtailment_mwh: "年弃电量/兆瓦时",
  annual_battery_charge_mwh: "储能年充电量/兆瓦时", annual_battery_discharge_mwh: "储能年放电量/兆瓦时",
  annual_storage_loss_mwh: "储能年损耗/兆瓦时", battery_initial_soc_mwh: "年初储能电量/兆瓦时",
  battery_final_soc_mwh: "年末储能电量/兆瓦时", annual_carbon_emissions_tco2: "运营碳排放/吨二氧化碳当量",
  max_bus_balance_error_mw: "最大母线平衡误差/兆瓦", max_system_balance_error_mw: "最大系统平衡误差/兆瓦",
  max_load_allocation_error_mw: "最大负荷分配误差/兆瓦",
};

const presentVersion = (value: unknown) => {
  const text = String(value ?? "--");
  if (text.includes("agri-park-fusion")) return `农业园区融合模型 ${text.split("-").at(-1)}`;
  if (text.includes("phase1-parameter-registry")) return "第一阶段参数台账 v1";
  if (text.includes("seasonal-baseline")) return "周期基线预测 v1";
  return text;
};

const fmt = (value: number | null | undefined, digits = 2) => value === null || value === undefined || Number.isNaN(value)
  ? "--"
  : value.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits });

function payloadKind(pageCode: string) {
  if (pageCode.startsWith("M07")) return "assets";
  if (pageCode.startsWith("M09")) return "parameters";
  if (["M06-06", "M06-07"].includes(pageCode)) return "stress";
  if (["M06-02", "M06-08", "M10-04", "M10-07"].includes(pageCode)) return "strategies";
  if (["M06-03", "M06-04", "M06-05", "M08-01", "M08-05", "M08-07", "M10-02", "M10-03"].includes(pageCode)) return "benefits";
  return "overview";
}

function loadPayload(pageCode: string, signal: AbortSignal): Promise<Payload> {
  const kind = payloadKind(pageCode);
  if (kind === "assets") return v2Api.assets(signal);
  if (kind === "parameters") return v2Api.parameters(signal);
  if (kind === "stress") return v2Api.stressTests(signal);
  if (kind === "strategies") return v2Api.strategies(signal);
  if (kind === "benefits") return v2Api.greenBenefits(signal);
  return v2Api.overview(signal);
}

function downloadPayload(page: NavPage, payload: Payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${page.code}-${page.title}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function AnalysisDataPage({ page }: AnalysisDataPageProps) {
  const loader = useCallback((signal: AbortSignal) => loadPayload(page.code, signal), [page.code]);
  const { data, loading, error } = useV2Resource(loader);
  const session = readSession();
  const canExport = !session || ["admin", "engineer"].includes(session.role);
  const meta = data?.meta as Record<string, string | number> | undefined;
  const metrics: Metric[] = [];
  const bars: Bar[] = [];
  let rows: Array<Record<string, string | number | boolean | null>> = [];
  let visualTitle = `${page.title}关键对比`;

  if (data && "annualSummary" in data) {
    const summary = data.annualSummary;
    metrics.push(
      { label: "年用电量", value: fmt(summary.annual_demand_mwh), unit: "兆瓦时", icon: <ThunderboltOutlined /> },
      { label: "物理绿电匹配率", value: fmt(summary.physical_green_match_rate_percent, 1), unit: "%", tone: "green", icon: <CheckCircleOutlined /> },
      { label: "年购普通电", value: fmt(summary.annual_grid_import_mwh), unit: "兆瓦时", tone: "amber", icon: <DatabaseOutlined /> },
      { label: "运营碳排放", value: fmt(summary.annual_carbon_emissions_tco2), unit: "吨", tone: "amber", icon: <SafetyCertificateOutlined /> },
      { label: "储能年放电", value: fmt(summary.annual_battery_discharge_mwh), unit: "兆瓦时", icon: <ThunderboltOutlined /> },
      { label: "最大平衡误差", value: fmt(summary.max_system_balance_error_mw, 8), unit: "兆瓦", tone: "green", icon: <CheckCircleOutlined /> },
    );
    const flowValues = [
      ["园区年用电", summary.annual_demand_mwh, "cyan"], ["本地光伏发电", summary.annual_pv_generation_mwh, "green"],
      ["直连绿电送达", summary.annual_direct_green_delivered_mwh, "green"], ["公共电网购电", summary.annual_grid_import_mwh, "amber"],
      ["储能放电", summary.annual_battery_discharge_mwh, "cyan"],
    ] as const;
    flowValues.forEach(([label, value, tone]) => bars.push({ label, value, display: `${fmt(value)} 兆瓦时`, tone }));
    rows = page.code === "M08-03" ? data.annualFlows : Object.entries(summary).map(([key, value]) => ({ 指标名称: ANNUAL_LABELS[key] ?? key, 数值: value }));
  } else if (data && "strategies" in data) {
    const summary = data.recommendedSummary;
    metrics.push(
      { label: "推荐光伏容量", value: fmt(data.recommendedCapacities.pv_capacity_mw), unit: "兆瓦", tone: "green", icon: <CheckCircleOutlined /> },
      { label: "推荐直连容量", value: fmt(data.recommendedCapacities.green_direct_capacity_mw), unit: "兆瓦", tone: "green", icon: <ThunderboltOutlined /> },
      { label: "推荐储能功率", value: fmt(data.recommendedCapacities.battery_power_mw), unit: "兆瓦", icon: <DatabaseOutlined /> },
      { label: "推荐储能容量", value: fmt(data.recommendedCapacities.battery_energy_mwh), unit: "兆瓦时", icon: <DatabaseOutlined /> },
      { label: "推荐方案年成本", value: fmt(summary.annual_total_cost_cny / 10000), unit: "万元", tone: "amber", icon: <DollarOutlined /> },
      { label: "推荐方案碳排放", value: fmt(summary.annual_carbon_emissions_tco2), unit: "吨", tone: "green", icon: <SafetyCertificateOutlined /> },
    );
    data.strategies.forEach((item) => bars.push({ label: String(item["策略"]), value: Number(item["年总成本/万元"]), display: `${fmt(Number(item["年总成本/万元"]))} 万元`, tone: "cyan" }));
    rows = data.strategies;
  } else if (data && "schemes" in data) {
    const baseline = data.schemes[0] ?? {};
    const target = data.schemes[data.schemes.length - 1] ?? {};
    const savings = Number(target["相对基准年节省/元"]);
    metrics.push(
      { label: "基准年成本", value: fmt(Number(baseline["年总成本/元"]) / 10000), unit: "万元", icon: <DollarOutlined /> },
      { label: "目标方案年成本", value: fmt(Number(target["年总成本/元"]) / 10000), unit: "万元", tone: "amber", icon: <DollarOutlined /> },
      { label: "相对基准年节省", value: fmt(savings / 10000), unit: "万元", tone: savings >= 0 ? "green" : "red", icon: <DollarOutlined /> },
      { label: "物理绿电匹配率", value: fmt(Number(target["物理绿电匹配率/%"]), 1), unit: "%", tone: "green", icon: <ThunderboltOutlined /> },
      { label: "运营碳排放", value: fmt(Number(target["运营碳排放/吨"])), unit: "吨", tone: "green", icon: <SafetyCertificateOutlined /> },
      { label: "当前绿证抵扣", value: "0", unit: "吨", icon: <AuditOutlined /> },
    );
    const key = page.code === "M06-04" || page.code === "M10-02" ? "相对基准年节省/元"
      : page.code === "M06-05" || page.code === "M08-07" ? "物理绿电匹配率/%"
        : page.code === "M08-01" ? "运营碳排放/吨" : "年总成本/元";
    data.schemes.forEach((item) => {
      const raw = Number(item[key]);
      const isMoney = key.endsWith("/元");
      bars.push({ label: String(item["方案"]), value: raw, display: isMoney ? `${fmt(raw / 10000)} 万元` : `${fmt(raw)} ${key.endsWith("/%") ? "%" : "吨"}`, tone: raw < 0 ? "red" : key.includes("绿电") ? "green" : "cyan" });
    });
    rows = page.code === "M06-04" ? data.attribution : data.schemes;
    if (page.code === "M08-05") visualTitle = "物理绿电与环境权益分离核算";
  } else if (data && "stressTests" in data) {
    const feasible = data.stressTests.filter((item) => item["是否可行"] === true).length;
    const zeroMaintained = data.stressTests.filter((item) => item["零碳是否保持"] === true).length;
    const worst = Math.max(...data.stressTests.map((item) => Number(item["相对基准成本变化/%"] ?? 0)));
    metrics.push(
      { label: "压力条件", value: fmt(data.stressTests.length, 0), unit: "项", icon: <SafetyCertificateOutlined /> },
      { label: "可行条件", value: fmt(feasible, 0), unit: "项", tone: feasible === data.stressTests.length ? "green" : "red", icon: <CheckCircleOutlined /> },
      { label: "保持零碳", value: fmt(zeroMaintained, 0), unit: "项", tone: "green", icon: <ThunderboltOutlined /> },
      { label: "最不利成本变化", value: fmt(worst), unit: "%", tone: "amber", icon: <DollarOutlined /> },
      { label: "固定容量检验", value: "是", unit: "", icon: <DatabaseOutlined /> },
      { label: "概率分位数", value: "未计算", unit: "", icon: <AuditOutlined /> },
    );
    data.stressTests.forEach((item) => bars.push({ label: String(item["压力条件"]), value: Number(item["年总成本/万元"] ?? 0), display: `${fmt(Number(item["年总成本/万元"] ?? 0))} 万元`, tone: item["零碳是否保持"] ? "green" : "red" }));
    rows = data.stressTests;
  } else if (data && "energyAssets" in data) {
    metrics.push(
      { label: "能源资产等值项", value: fmt(data.energyAssets.length, 0), unit: "项", icon: <ThunderboltOutlined /> },
      { label: "农业资产等值项", value: fmt(data.agriculturalAssets.length, 0), unit: "项", icon: <ApartmentOutlined /> },
      { label: "应建计量点", value: fmt(data.meters.length, 0), unit: "个", tone: "amber", icon: <DatabaseOutlined /> },
      { label: "已接入计量点", value: "0", unit: "个", tone: "red", icon: <DatabaseOutlined /> },
      { label: "拓扑关系", value: fmt(data.topology.length, 0), unit: "条", icon: <ApartmentOutlined /> },
      { label: "现场核验完成率", value: "0.0", unit: "%", tone: "red", icon: <SafetyCertificateOutlined /> },
    );
    const pageRows: Record<string, Array<Record<string, string | number | null>>> = { "M07-01": data.energyAssets, "M07-02": data.agriculturalAssets, "M07-03": data.topology, "M07-04": data.meters };
    rows = pageRows[page.code] ?? [...data.energyAssets, ...data.agriculturalAssets];
    [...data.energyAssets, ...data.agriculturalAssets].forEach((item) => bars.push({ label: String(item.assetName), value: Number(item.ratedPower), display: `${fmt(Number(item.ratedPower))} ${String(item.powerUnit)}`, tone: String(item.assetType).includes("光伏") || String(item.assetType).includes("直连") ? "green" : "cyan" }));
  } else if (data && "parameters" in data) {
    const pending = data.parameters.filter((item) => item.verification_status === "待补充");
    const demo = data.parameters.filter((item) => item.verification_status === "演示参数");
    const groups = new Set(data.parameters.map((item) => item.group));
    metrics.push(
      { label: "参数总数", value: fmt(data.parameters.length, 0), unit: "项", icon: <DatabaseOutlined /> },
      { label: "参数分组", value: fmt(groups.size, 0), unit: "组", icon: <ApartmentOutlined /> },
      { label: "正式资料缺口", value: fmt(pending.length, 0), unit: "项", tone: "red", icon: <SafetyCertificateOutlined /> },
      { label: "演示参数", value: fmt(demo.length, 0), unit: "项", tone: "amber", icon: <AuditOutlined /> },
      { label: "人民币参数", value: fmt(data.parameters.filter((item) => item.unit.includes("元")).length, 0), unit: "项", icon: <DollarOutlined /> },
      { label: "参数版本", value: "台账 v1", unit: "", icon: <CheckCircleOutlined /> },
    );
    Array.from(groups).forEach((group) => { const count = data.parameters.filter((item) => item.group === group).length; bars.push({ label: group, value: count, display: `${count} 项`, tone: "cyan" }); });
    rows = page.code === "M09-02" ? pending : data.parameters;
  }

  const columns = rows.length ? Object.keys(rows[0]).slice(0, 9).map((key) => ({
    title: FIELD_LABELS[key] ?? key, dataIndex: key, key, ellipsis: true,
    render: (value: unknown) => {
      if (value === null || value === undefined || value === "") return "--";
      if (typeof value === "boolean") return value ? "是" : "否";
      if (typeof value === "number") return value.toLocaleString("zh-CN", { maximumFractionDigits: 6 });
      return String(value);
    },
  })) : [];

  return (
    <main className={`business-page analysis-page analysis-page--${page.kind}`}>
      {error ? <Alert className="data-state-alert" type="error" showIcon message="接口暂不可用" description={error} /> : (
        <Alert className="data-state-alert" type="warning" showIcon message={`${page.code} ${page.title} · ${String(meta?.dataStatus ?? "读取中")}`} description={page.description} action={data ? <Button icon={<DownloadOutlined />} disabled={!canExport} title={canExport ? "" : "当前角色没有报告导出权限"} onClick={() => downloadPayload(page, data)}>导出当前结果</Button> : undefined} />
      )}
      {loading ? <Skeleton active paragraph={{ rows: 12 }} /> : (
        <>
          <div className="metric-grid workspace-metric-grid">{metrics.map((item) => <MetricCard key={item.label} {...item} meta="可追溯计算结果" />)}</div>
          <div className="workspace-main-grid">
            <Panel title={visualTitle}><ComparisonBars items={bars.slice(0, 12)} /></Panel>
            <Panel title="数据与核算状态">
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="数据状态"><Tag color={String(meta?.dataStatus).includes("待") ? "error" : "warning"}>{String(meta?.dataStatus ?? "未知")}</Tag></Descriptions.Item>
                <Descriptions.Item label="数据来源">{String(meta?.sourceReference ?? "模型与参数台账")}</Descriptions.Item>
                <Descriptions.Item label="模型版本">{presentVersion(meta?.modelVersion ?? "本页不使用模型")}</Descriptions.Item>
                <Descriptions.Item label="参数版本">{presentVersion(meta?.parameterVersion)}</Descriptions.Item>
                <Descriptions.Item label="金额单位">人民币</Descriptions.Item>
                <Descriptions.Item label="权益边界">物理绿电与绿证分开核算</Descriptions.Item>
              </Descriptions>
            </Panel>
          </div>
          <Panel title={`${page.title}数据明细`}><Table columns={columns} dataSource={rows.map((row, index) => ({ key: index, ...row }))} pagination={{ pageSize: 8 }} size="small" scroll={{ x: true }} /></Panel>
        </>
      )}
    </main>
  );
}
