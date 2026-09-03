import { useCallback } from "react";
import { ApiOutlined, AuditOutlined, CheckCircleOutlined, CloudServerOutlined, DatabaseOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Alert, Descriptions, Skeleton, Table, Tag } from "antd";
import { ComparisonBars } from "../components/ComparisonBars";
import { MetricCard } from "../components/MetricCard";
import { Panel } from "../components/Panel";
import { useV2Resource } from "../hooks/useV2Resource";
import { v2Api } from "../services/api";
import type { NavPage } from "../types";

interface SystemStatusPageProps { page: NavPage }

const LABELS: Record<string, string> = {
  organization: "组织", park: "园区", parkStatus: "园区状态", dataDomain: "数据域",
  username: "账号", displayName: "姓名", role: "角色编码", active: "是否启用", name: "名称", permissions: "权限范围",
  kind: "模型类型", display_name: "模型名称", version: "版本", engine: "求解引擎", description: "说明",
  path: "接口路径", method: "操作方式", status: "状态", rule: "规则", threshold: "判定条件", severity: "级别",
  quantity: "物理量", unit: "中文单位", symbol: "符号", component: "组件", detail: "状态说明",
  id: "任务编号", project_id: "项目编号", scenario_version_id: "场景版本", progress: "进度/%", created_by: "创建人", created_at: "创建时间",
  actor_id: "操作人", action: "操作", entity_type: "对象类型", entity_id: "对象编号", details: "详情",
  format: "备份格式", backupCount: "备份数量", lastBackup: "最近备份", lastBackupAt: "最近备份时间", verification: "校验机制", restoreProtection: "恢复保护",
  taskStatus: "任务状态", count: "数量",
};

const roleName = (role?: string) => ({ admin: "系统管理员", engineer: "规划与调度工程师", operator: "运行值班员", viewer: "只读用户", auditor: "审计用户" }[role ?? ""] ?? role ?? "--");

export function SystemStatusPage({ page }: SystemStatusPageProps) {
  const loader = useCallback((signal: AbortSignal) => v2Api.systemStatus(signal), []);
  const { data, loading, error } = useV2Resource(loader);
  const jobTotal = Object.values(data?.jobStatusCounts ?? {}).reduce((sum, value) => sum + value, 0);
  const healthy = data?.components.filter((item) => ["在线", "可用", "已配置", "已有备份"].includes(String(item.status))).length ?? 0;
  const pending = (data?.components.length ?? 0) - healthy;
  const statusRows = Object.entries(data?.jobStatusCounts ?? {}).map(([taskStatus, count]) => ({ taskStatus, count }));
  const rowsByPage: Record<string, Array<Record<string, unknown>>> = data ? {
    "M11-01": data.organizations,
    "M11-02": data.accounts,
    "M11-03": data.roles,
    "M11-04": data.models,
    "M11-05": data.interfaces,
    "M11-06": data.alertRules,
    "M11-07": data.units,
    "M11-08": data.jobs.length ? data.jobs : statusRows,
    "M11-09": data.components,
    "M11-10": [data.backup],
    "M11-11": data.auditEvents,
  } : {};
  const rows = rowsByPage[page.code] ?? [];
  const columns = rows.length ? Object.keys(rows[0]).filter((key) => key !== "request").slice(0, 9).map((key) => ({
    title: LABELS[key] ?? key,
    dataIndex: key,
    key,
    ellipsis: true,
    render: (value: unknown) => {
      if (value === null || value === undefined || value === "") return "--";
      if (typeof value === "boolean") return value ? "是" : "否";
      if (typeof value === "object") return JSON.stringify(value);
      if (key === "role") return roleName(String(value));
      return String(value);
    },
  })) : [];
  const bars = (data?.components ?? []).map((item) => ({
    label: String(item.component),
    value: ["在线", "可用", "已配置", "已有备份"].includes(String(item.status)) ? 1 : 0.35,
    display: String(item.status),
    tone: ["在线", "可用", "已配置", "已有备份"].includes(String(item.status)) ? "green" as const : "amber" as const,
  }));

  return (
    <main className="business-page system-status-page">
      {error ? <Alert className="data-state-alert" type="error" showIcon message="系统状态接口暂不可用" description={error} /> : (
        <Alert className="data-state-alert" type="info" showIcon message={`${page.code} ${page.title} · ${String(data?.meta.dataStatus ?? "读取中")}`} description={page.description} />
      )}
      {loading ? <Skeleton active paragraph={{ rows: 12 }} /> : data ? (
        <>
          <div className="metric-grid workspace-metric-grid">
            <MetricCard label="系统组件" value={String(data.components.length)} unit="项" icon={<CloudServerOutlined />} meta="实时状态" />
            <MetricCard label="健康组件" value={String(healthy)} unit="项" tone="green" icon={<CheckCircleOutlined />} meta="实时状态" />
            <MetricCard label="待处理组件" value={String(pending)} unit="项" tone={pending ? "amber" : "green"} icon={<SafetyCertificateOutlined />} meta="实时状态" />
            <MetricCard label="优化任务" value={String(jobTotal)} unit="项" icon={<DatabaseOutlined />} meta="持久任务队列" />
            <MetricCard label="配置账号" value={String(data.auth.configuredAccountCount)} unit="个" icon={<ApiOutlined />} meta={String(data.auth.modeName)} />
            <MetricCard label="审计事件" value={String(data.auditEvents.length)} unit="条" icon={<AuditOutlined />} meta="当前可见范围" />
          </div>
          <div className="workspace-main-grid">
            <Panel title="系统组件健康度"><ComparisonBars items={bars} /></Panel>
            <Panel title="身份与运行边界">
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="当前用户">{data.currentUser.userId}</Descriptions.Item>
                <Descriptions.Item label="当前角色"><Tag color="blue">{roleName(data.currentUser.role)}</Tag></Descriptions.Item>
                <Descriptions.Item label="认证模式">{String(data.auth.modeName)}</Descriptions.Item>
                <Descriptions.Item label="令牌有效期">{String(data.auth.tokenTtlSeconds)} 秒</Descriptions.Item>
                <Descriptions.Item label="状态时点">{String(data.meta.asOf)}</Descriptions.Item>
                <Descriptions.Item label="金额单位">人民币</Descriptions.Item>
              </Descriptions>
            </Panel>
          </div>
          <Panel title={`${page.title}明细`}><Table columns={columns} dataSource={rows.map((row, index) => ({ key: index, ...row }))} pagination={{ pageSize: 8 }} size="small" scroll={{ x: true }} locale={{ emptyText: "当前没有可显示记录" }} /></Panel>
        </>
      ) : null}
    </main>
  );
}
