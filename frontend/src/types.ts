export type PageKind =
  | "monitor"
  | "production"
  | "forecast"
  | "dispatch"
  | "planning"
  | "asset"
  | "carbon"
  | "data"
  | "report"
  | "system";

export interface NavPage {
  code: string;
  title: string;
  description: string;
  path: string;
  kind: PageKind;
  badge?: number;
}

export interface NavGroup {
  key: string;
  title: string;
  pages: NavPage[];
}

export type DataStatus = "实时" | "延迟" | "演示" | "估算" | "未接入";

export interface EvidenceMeta {
  parkId: string;
  asOf: string | null;
  dataStatus: DataStatus;
  sourceIds: string[];
  qualityCode: string;
  runId?: string;
  modelVersion?: string;
  parameterVersion?: string;
  currency: "CNY";
}
