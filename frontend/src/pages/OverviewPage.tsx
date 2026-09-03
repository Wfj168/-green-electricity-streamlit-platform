import { useCallback } from "react";
import {
  AlertOutlined,
  AreaChartOutlined,
  CloudOutlined,
  DashboardOutlined,
  FieldTimeOutlined,
  PieChartOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Alert, Progress, Skeleton, Tag } from "antd";
import { MetricCard } from "../components/MetricCard";
import { Panel } from "../components/Panel";
import { SimpleLineChart } from "../components/SimpleLineChart";
import { useV2Resource } from "../hooks/useV2Resource";

const presentVersion = (value?: string) => {
  if (value?.includes("agri-park-fusion")) return "农业园区融合模型 v2.1";
  if (value?.includes("phase1-parameter-registry")) return "第一阶段参数台账 v1";
  return value ?? "--";
};
import { v2Api } from "../services/api";

const fmt = (value?: number | null, digits = 2) =>
  value === undefined || value === null || !Number.isFinite(value)
    ? "--"
    : value.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function OverviewPage() {
  const loader = useCallback((signal: AbortSignal) => v2Api.overview(signal), []);
  const { data, loading, error } = useV2Resource(loader);
  const metric = data?.metrics;
  const summary = data?.annualSummary;

  return (
    <main className="dashboard-page">
      {error ? (
        <Alert className="data-state-alert" type="error" showIcon message="模型接口暂不可用" description={error} />
      ) : (
        <Alert
          className="data-state-alert"
          type={data?.meta.dataStatus === "演示" ? "warning" : "success"}
          showIcon
          message={loading ? "正在读取模型结果" : `${data?.meta.dataStatus}数据 · ${data?.meta.sourceReference}`}
          description={data ? `数据时点：${data.meta.asOf}；任务：2025年度园区能量流计算；模型：${presentVersion(data.meta.modelVersion)}` : undefined}
        />
      )}
      {loading ? <Skeleton active paragraph={{ rows: 8 }} /> : (
        <>
          <div className="metric-grid metric-grid--seven">
            <MetricCard label="园区总负荷" value={fmt(metric?.totalLoadMw)} unit="兆瓦" meta="模型峰值代表时段" icon={<DashboardOutlined />} />
            <MetricCard label="光伏出力" value={fmt(metric?.pvPowerMw)} unit="兆瓦" tone="green" meta="本地物理绿电" icon={<CloudOutlined />} />
            <MetricCard label="直连绿电送达" value={fmt(metric?.directDeliveredMw)} unit="兆瓦" tone="green" meta={`送端 ${fmt(metric?.directInjectedMw)} 兆瓦`} icon={<ThunderboltOutlined />} />
            <MetricCard label="储能荷电状态" value={fmt(metric?.storageSocPercent, 1)} unit="%" meta="按来源分账" icon={<AreaChartOutlined />} />
            <MetricCard label="小时物理绿电占比" value={fmt(metric?.physicalGreenSharePercent, 1)} unit="%" tone="green" meta="不含绿证抵扣" icon={<PieChartOutlined />} />
            <MetricCard label="小时碳排放" value={fmt(metric?.carbonRateTco2PerHour, 3)} unit="吨二氧化碳当量" tone="amber" meta="范围二运行排放" icon={<FieldTimeOutlined />} />
            <MetricCard label="待核验参数" value={fmt(data?.meta.formalReadinessGapCount, 0)} unit="项" tone="red" meta="正式项目资料缺口" icon={<AlertOutlined />} />
          </div>

          <div className="dashboard-main-grid">
            <Panel title="园区实时能量流" extra={<Tag color="warning">{data?.meta.dataStatus ?? "未接入"}</Tag>}>
              <div className="energy-flow">
                <div className="flow-column">
                  <div className="flow-node flow-node--green">本地光伏<br /><strong>{fmt(metric?.pvPowerMw)} 兆瓦</strong></div>
                  <div className="flow-node flow-node--green">直连绿电<br /><strong>{fmt(metric?.directDeliveredMw)} 兆瓦</strong></div>
                  <div className="flow-node">公共电网<br /><strong>{fmt(metric?.gridImportMw)} 兆瓦</strong></div>
                </div>
                <div className="flow-arrow">→</div>
                <div className="flow-node flow-node--center">园区交流母线<br /><strong>误差 {fmt(metric?.busBalanceErrorMw, 8)} 兆瓦</strong></div>
                <div className="flow-arrow">→</div>
                <div className="flow-column">
                  <div className="flow-node">农业生产负荷<br /><strong>{fmt(metric?.totalLoadMw)} 兆瓦</strong></div>
                  <div className="flow-node">储能净出力<br /><strong>{fmt(metric?.storagePowerMw)} 兆瓦</strong></div>
                  <div className="flow-node">上网与弃电<br /><strong>{fmt((metric?.exportMw ?? 0) + (metric?.curtailmentMw ?? 0))} 兆瓦</strong></div>
                </div>
              </div>
              <div className="balance-summary">
                <div><span>送端注入</span><strong>{fmt(metric?.directInjectedMw)}</strong><em>兆瓦</em></div>
                <div><span>受端送达</span><strong>{fmt(metric?.directDeliveredMw)}</strong><em>兆瓦</em></div>
                <div><span>线路损耗</span><strong>{fmt(metric?.directLineLossMw)}</strong><em>兆瓦</em></div>
                <div><span>平衡误差</span><strong>{fmt(metric?.busBalanceErrorMw, 8)}</strong><em>兆瓦</em></div>
              </div>
            </Panel>

            <Panel title="农业负荷与任务执行">
              <div className="load-list">
                {(data?.loads ?? []).map((load) => (
                  <div className="load-row" key={load.code}>
                    <div><strong>{load.name}</strong><span>{load.taskStatus}</span></div>
                    <Progress percent={load.sharePercent} showInfo={false} strokeColor="#2ebcff" trailColor="#123b5a" />
                    <em>{fmt(load.powerMw)} 兆瓦</em>
                  </div>
                ))}
              </div>
            </Panel>
          </div>

          <div className="dashboard-bottom-grid">
            <Panel title="年度能源结构">
              <div className="annual-stat-list">
                <div><span>全年负荷</span><strong>{fmt(summary?.annual_demand_mwh, 0)} 兆瓦时</strong></div>
                <div><span>物理绿电供负荷</span><strong>{fmt(summary?.annual_physical_green_to_load_mwh, 0)} 兆瓦时</strong></div>
                <div><span>公共电网购电</span><strong>{fmt(summary?.annual_grid_import_mwh, 0)} 兆瓦时</strong></div>
                <div><span>弃电</span><strong>{fmt(summary?.annual_curtailment_mwh, 0)} 兆瓦时</strong></div>
              </div>
            </Panel>
            <Panel title="24小时供需趋势">
              <SimpleLineChart unit="兆瓦" series={[
                { name: "农业负荷", color: "#2ebcff", values: (data?.trend ?? []).map((row) => row.loadMw) },
                { name: "物理绿电", color: "#35d07f", values: (data?.trend ?? []).map((row) => row.physicalGreenMw) },
                { name: "公共电网", color: "#f6b84b", values: (data?.trend ?? []).map((row) => row.gridMw) },
              ]} />
            </Panel>
            <Panel title="绿电与碳排表现">
              <div className="annual-stat-list annual-stat-list--large">
                <div><span>物理绿电匹配率</span><strong>{fmt(summary?.physical_green_match_rate_percent, 2)}%</strong></div>
                <div><span>年度运营碳排放</span><strong>{fmt(summary?.annual_carbon_emissions_tco2, 2)} 吨</strong></div>
                <div><span>直连线路损耗</span><strong>{fmt(summary?.annual_direct_green_line_loss_mwh, 2)} 兆瓦时</strong></div>
              </div>
            </Panel>
            <Panel title="数据可追溯性">
              <div className="freshness-grid"><strong>{data ? "合成数据已完成平衡校核" : "未接入"}</strong><span>模型：{presentVersion(data?.meta.modelVersion)}<br />参数：{presentVersion(data?.meta.parameterVersion)}<br />币种：人民币</span></div>
            </Panel>
          </div>
        </>
      )}
    </main>
  );
}
