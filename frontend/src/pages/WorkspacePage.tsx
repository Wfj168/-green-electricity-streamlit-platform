import {
  ApiOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FundProjectionScreenOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Alert, Button, Descriptions, Select, Table, Tag } from "antd";
import { MetricCard } from "../components/MetricCard";
import { Panel } from "../components/Panel";
import type { NavPage } from "../types";

interface WorkspacePageProps { page: NavPage }

const evidenceColumns = [
  { title: "证据项", dataIndex: "name", key: "name" },
  { title: "当前状态", dataIndex: "status", key: "status", render: () => <Tag>未接入</Tag> },
  { title: "要求", dataIndex: "requirement", key: "requirement" },
];

const evidenceRows = [
  { key: "source", name: "数据来源", requirement: "测点、文件、合同或上游系统标识" },
  { key: "quality", name: "数据质量", requirement: "完整性、及时性、合理性与平衡性" },
  { key: "version", name: "结果版本", requirement: "任务、模型与参数快照版本" },
];

export function WorkspacePage({ page }: WorkspacePageProps) {
  return (
    <main className={`business-page workspace-page workspace-page--${page.kind}`}>
      <div className="context-filter">
        <span className="filter-label">当前园区</span>
        <Select value="零碳农业示范园区" options={[{ value: "零碳农业示范园区", label: "零碳农业示范园区" }]} />
        <Select value="当前周期" options={[{ value: "当前周期", label: "当前周期" }]} />
        <div className="context-filter-actions"><Button type="primary" disabled>运行或刷新</Button></div>
      </div>
      <Alert
        className="data-state-alert"
        type="warning"
        showIcon
        message={`${page.code} ${page.title}：页面框架已创建，真实接口尚未接入。`}
        description={page.description}
      />
      <div className="metric-grid workspace-metric-grid">
        <MetricCard label="核心指标一" icon={<FundProjectionScreenOutlined />} />
        <MetricCard label="核心指标二" tone="green" icon={<CheckCircleOutlined />} />
        <MetricCard label="核心指标三" icon={<DatabaseOutlined />} />
        <MetricCard label="异常与风险" tone="amber" icon={<SafetyCertificateOutlined />} />
        <MetricCard label="数据覆盖率" unit="%" icon={<ApiOutlined />} />
        <MetricCard label="待处理事项" unit="项" tone="red" icon={<FileSearchOutlined />} />
      </div>
      <div className="workspace-main-grid">
        <Panel title={`${page.title}业务视图`}>
          <div className="workspace-canvas">
            <span className="canvas-code">{page.code}</span>
            <strong>{page.title}</strong>
            <p>{page.description}</p>
            <em>这里将接入数据库、实时测点或模型任务结果，不使用页面固定数字。</em>
          </div>
        </Panel>
        <Panel title="数据与模型状态">
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="数据状态">未接入</Descriptions.Item>
            <Descriptions.Item label="数据时点">--</Descriptions.Item>
            <Descriptions.Item label="任务编号">--</Descriptions.Item>
            <Descriptions.Item label="模型版本">--</Descriptions.Item>
            <Descriptions.Item label="参数版本">--</Descriptions.Item>
            <Descriptions.Item label="金额单位">人民币</Descriptions.Item>
          </Descriptions>
        </Panel>
      </div>
      <Panel title="来源与可追溯性">
        <Table columns={evidenceColumns} dataSource={evidenceRows} pagination={false} size="small" />
      </Panel>
    </main>
  );
}
