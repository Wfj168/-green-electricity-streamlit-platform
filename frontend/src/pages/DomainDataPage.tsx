import { useCallback, type ReactNode } from "react";
import {
  AreaChartOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  FieldTimeOutlined,
  FundProjectionScreenOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Alert, Descriptions, Skeleton, Table, Tag } from "antd";
import { MetricCard } from "../components/MetricCard";
import { Panel } from "../components/Panel";
import { SimpleLineChart } from "../components/SimpleLineChart";
import { useV2Resource } from "../hooks/useV2Resource";
import { v2Api, type ForecastCenterData, type OverviewData, type StrategyData } from "../services/api";
import type { NavPage } from "../types";

interface DomainDataPageProps { page: NavPage }
type DomainPayload = OverviewData | ForecastCenterData | StrategyData;

const fmt = (value?: number, digits = 2) => value === undefined
  ? "--"
  : value.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits });

const FIELD_LABELS: Record<string, string> = {
  code: "编码",
  name: "名称",
  powerMw: "当前功率/兆瓦",
  sharePercent: "负荷占比/%",
  taskProgressPercent: "任务进度/%",
  taskStatus: "任务状态",
  model: "预测方法",
  MAE: "平均绝对误差",
  RMSE: "均方根误差",
  "sMAPE [%]": "对称百分比误差/%",
  validation_points: "验证点数",
  timestamp: "时间",
  totalLoadMw: "园区负荷/兆瓦",
  irrigationMw: "灌溉负荷/兆瓦",
  processingMw: "加工负荷/兆瓦",
  coldStorageMw: "冷链负荷/兆瓦",
  auxiliaryMw: "辅助负荷/兆瓦",
  pvMw: "光伏出力/兆瓦",
  directDeliveredMw: "直连送达/兆瓦",
  storageChargeMw: "储能充电/兆瓦",
  storageDischargeMw: "储能放电/兆瓦",
  storageSocMwh: "储能电量/兆瓦时",
  gridMw: "电网购电/兆瓦",
  exportMw: "上网功率/兆瓦",
  curtailmentMw: "弃电功率/兆瓦",
  balanceErrorMw: "平衡误差/兆瓦",
};

const MODEL_LABELS: Record<string, string> = {
  seasonal_naive: "同期同刻基线",
  previous_day: "前一日同刻基线",
  moving_average: "滚动均值基线",
};

const presentVersion = (value: unknown) => {
  const text = String(value ?? "--");
  if (text.includes("agri-park-fusion")) return "农业园区融合模型 v2.1";
  if (text.includes("phase1-parameter-registry")) return "第一阶段参数台账 v1";
  if (text.includes("seasonal-baseline")) return "周期基线预测 v1";
  return text;
};

function isOverview(data: DomainPayload): data is OverviewData { return "metrics" in data; }
function isForecast(data: DomainPayload): data is ForecastCenterData { return "series" in data; }
function isStrategy(data: DomainPayload): data is StrategyData { return "strategies" in data; }

export function DomainDataPage({ page }: DomainDataPageProps) {
  const loader = useCallback((signal: AbortSignal): Promise<DomainPayload> => {
    if (page.code.startsWith("M04")) return v2Api.forecasts(signal);
    if (page.code.startsWith("M05")) return v2Api.strategies(signal);
    return v2Api.overview(signal);
  }, [page.code]);
  const { data, loading, error } = useV2Resource(loader);

  const meta = data?.meta as Record<string, string | number> | undefined;
  let chartSeries: Array<{ name: string; color: string; values: number[] }> = [];
  let chartUnit = "兆瓦";
  let rows: Array<Record<string, string | number | null>> = [];
  let metrics: Array<{ label: string; value: string; unit: string; tone?: "green" | "amber"; icon: ReactNode }> = [];

  if (data && isOverview(data)) {
    chartSeries = [
      { name: "农业负荷", color: "#2ebcff", values: data.trend.map((row) => row.loadMw) },
      { name: "光伏", color: "#35d07f", values: data.trend.map((row) => row.pvMw) },
      { name: "直连送达", color: "#7b94ff", values: data.trend.map((row) => row.directDeliveredMw) },
      { name: "公共电网", color: "#f6b84b", values: data.trend.map((row) => row.gridMw) },
    ];
    rows = page.code.startsWith("M03") ? data.loadSummary : data.loads;
    metrics = [
      { label: "园区总负荷", value: fmt(data.metrics.totalLoadMw), unit: "兆瓦", icon: <AreaChartOutlined /> },
      { label: "光伏出力", value: fmt(data.metrics.pvPowerMw), unit: "兆瓦", tone: "green", icon: <CheckCircleOutlined /> },
      { label: "直连绿电送达", value: fmt(data.metrics.directDeliveredMw), unit: "兆瓦", tone: "green", icon: <ThunderboltOutlined /> },
      { label: "公共电网购电", value: fmt(data.metrics.gridImportMw), unit: "兆瓦", tone: "amber", icon: <FundProjectionScreenOutlined /> },
      { label: "物理绿电占比", value: fmt(data.metrics.physicalGreenSharePercent, 1), unit: "%", tone: "green", icon: <CheckCircleOutlined /> },
      { label: "母线平衡误差", value: fmt(data.metrics.busBalanceErrorMw, 8), unit: "兆瓦", icon: <DatabaseOutlined /> },
    ];
  } else if (data && isForecast(data)) {
    const forecastPageIndex: Record<string, number> = {
      "M04-01": 0,
      "M04-02": 1,
      "M04-03": 2,
      "M04-04": 3,
      "M04-05": 4,
      "M04-06": 5,
      "M04-07": 0,
    };
    const seriesIndex = forecastPageIndex[page.code] ?? 0;
    const selected = data.series[seriesIndex];
    chartUnit = selected.unit;
    chartSeries = [{ name: selected.name, color: "#2ebcff", values: selected.values.map((row) => row.value) }];
    rows = selected.evaluation;
    const best = selected.evaluation.find((item) => item.model === selected.modelName) ?? {};
    metrics = [
      { label: "预测点数", value: fmt(selected.values.length, 0), unit: "个", icon: <AreaChartOutlined /> },
      { label: "时间间隔", value: fmt(Number(data.meta.intervalMinutes), 0), unit: "分钟", icon: <FieldTimeOutlined /> },
      { label: "平均绝对误差", value: fmt(Number(best.MAE)), unit: selected.unit, tone: "green", icon: <CheckCircleOutlined /> },
      { label: "均方根误差", value: fmt(Number(best.RMSE)), unit: selected.unit, icon: <FundProjectionScreenOutlined /> },
      { label: "对称百分比误差", value: fmt(Number(best["sMAPE [%]"])), unit: "%", tone: "amber", icon: <DatabaseOutlined /> },
      { label: "预测版本", value: "基线 v1", unit: "", icon: <DatabaseOutlined /> },
    ];
  } else if (data && isStrategy(data)) {
    chartSeries = [
      { name: "农业负荷", color: "#2ebcff", values: data.dayAheadPlan.map((row) => Number(row.totalLoadMw)) },
      { name: "光伏", color: "#35d07f", values: data.dayAheadPlan.map((row) => Number(row.pvMw)) },
      { name: "直连送达", color: "#7b94ff", values: data.dayAheadPlan.map((row) => Number(row.directDeliveredMw)) },
      { name: "储能放电", color: "#f6b84b", values: data.dayAheadPlan.map((row) => Number(row.storageDischargeMw)) },
    ];
    rows = data.dayAheadPlan.slice(0, 12);
    metrics = [
      { label: "推荐光伏容量", value: fmt(data.recommendedCapacities.pv_capacity_mw), unit: "兆瓦", tone: "green", icon: <CheckCircleOutlined /> },
      { label: "推荐直连容量", value: fmt(data.recommendedCapacities.green_direct_capacity_mw), unit: "兆瓦", tone: "green", icon: <ThunderboltOutlined /> },
      { label: "推荐储能功率", value: fmt(data.recommendedCapacities.battery_power_mw), unit: "兆瓦", icon: <AreaChartOutlined /> },
      { label: "推荐储能容量", value: fmt(data.recommendedCapacities.battery_energy_mwh), unit: "兆瓦时", icon: <DatabaseOutlined /> },
      { label: "年总成本", value: fmt(data.recommendedSummary.annual_total_cost_cny / 10000), unit: "万元", tone: "amber", icon: <FundProjectionScreenOutlined /> },
      { label: "任务最大误差", value: fmt(data.recommendedSummary.max_daily_production_task_energy_error_mwh, 8), unit: "兆瓦时", icon: <CheckCircleOutlined /> },
    ];
  }

  const columns = rows.length
    ? Object.keys(rows[0]).slice(0, 7).map((key) => ({
      title: FIELD_LABELS[key] ?? key,
      dataIndex: key,
      key,
      ellipsis: true,
      render: (value: string | number | null) => {
        if (value === null || value === undefined) return "--";
        if (key === "model") return MODEL_LABELS[String(value)] ?? value;
        if (key === "timestamp") return new Date(String(value)).toLocaleString("zh-CN", { hour12: false });
        if (typeof value === "number") return value.toLocaleString("zh-CN", { maximumFractionDigits: 6 });
        return value;
      },
    }))
    : [];
  const tableRows = rows.map((row, index) => ({ key: index, ...row }));

  return (
    <main className={`business-page domain-page domain-page--${page.kind}`}>
      {error ? <Alert className="data-state-alert" type="error" showIcon message="接口暂不可用" description={error} /> : (
        <Alert className="data-state-alert" type="warning" showIcon message={`${page.code} ${page.title} · ${String(meta?.dataStatus ?? "读取中")}`} description={page.description} />
      )}
      {loading ? <Skeleton active paragraph={{ rows: 10 }} /> : (
        <>
          <div className="metric-grid workspace-metric-grid">
            {metrics.map((item) => <MetricCard key={item.label} {...item} tone={item.tone} meta="模型计算结果" />)}
          </div>
          <div className="workspace-main-grid">
            <Panel title={`${page.title}趋势分析`}><SimpleLineChart unit={chartUnit} series={chartSeries} /></Panel>
            <Panel title="数据与模型状态">
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="数据状态"><Tag color="warning">{String(meta?.dataStatus ?? "未知")}</Tag></Descriptions.Item>
                <Descriptions.Item label="数据来源">{String(meta?.sourceReference ?? "模型结果")}</Descriptions.Item>
                <Descriptions.Item label="模型版本">{presentVersion(meta?.modelVersion)}</Descriptions.Item>
                <Descriptions.Item label="参数版本">{presentVersion(meta?.parameterVersion)}</Descriptions.Item>
                <Descriptions.Item label="金额单位">人民币</Descriptions.Item>
              </Descriptions>
            </Panel>
          </div>
          <Panel title={`${page.title}数据明细`}>
            <Table columns={columns} dataSource={tableRows} pagination={{ pageSize: 8 }} size="small" scroll={{ x: true }} />
          </Panel>
        </>
      )}
    </main>
  );
}
