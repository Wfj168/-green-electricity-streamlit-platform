import { readSession } from "./session";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export interface OverviewData {
  meta: {
    parkId: string;
    parkName: string;
    asOf: string;
    dataStatus: string;
    sourceIds: string[];
    sourceReference: string;
    qualityCode: string;
    runId: string;
    modelVersion: string;
    parameterVersion: string;
    currency: "CNY";
    formalReadinessGapCount: number;
  };
  metrics: {
    totalLoadMw: number;
    pvPowerMw: number;
    directInjectedMw: number;
    directDeliveredMw: number;
    directLineLossMw: number;
    storagePowerMw: number;
    storageSocPercent: number;
    physicalGreenSharePercent: number;
    carbonRateTco2PerHour: number;
    gridImportMw: number;
    exportMw: number;
    curtailmentMw: number;
    busBalanceErrorMw: number;
  };
  loads: Array<{
    code: string;
    name: string;
    powerMw: number;
    sharePercent: number;
    taskProgressPercent: number | null;
    taskStatus: string;
  }>;
  trend: Array<{
    timestamp: string;
    loadMw: number;
    pvMw: number;
    directDeliveredMw: number;
    gridMw: number;
    storageChargeMw: number;
    storageDischargeMw: number;
    physicalGreenMw: number;
  }>;
  annualSummary: Record<string, number>;
  loadSummary: Array<Record<string, string | number>>;
  annualFlows: Array<Record<string, string | number>>;
}

export interface ForecastCenterData {
  meta: Record<string, string | number>;
  series: Array<{
    code: string;
    name: string;
    unit: string;
    versionId: string;
    modelName: string;
    trainingStart: string;
    trainingEnd: string;
    validationStart: string;
    validationEnd: string;
    evaluation: Array<Record<string, string | number>>;
    values: Array<{ timestamp: string; value: number }>;
  }>;
}

export interface StrategyData {
  meta: Record<string, string | number>;
  strategies: Array<Record<string, string | number>>;
  recommendedCapacities: Record<string, number>;
  recommendedSummary: Record<string, number>;
  recommendedCostBreakdown: Record<string, number>;
  dayAheadPlan: Array<Record<string, string | number>>;
}

export interface ParametersData {
  meta: Record<string, string | number>;
  parameters: Array<{
    code: string;
    name: string;
    group: string;
    unit: string;
    value: number | null;
    minimum: number | null;
    maximum: number | null;
    source_grade: string;
    verification_status: string;
    source_reference: string;
    setting_method: string;
    formal_required: boolean;
  }>;
}

export interface StressTestData {
  meta: Record<string, string | number>;
  stressTests: Array<Record<string, string | number | boolean | null>>;
}

export interface GreenBenefitData {
  meta: Record<string, string | number>;
  schemes: Array<Record<string, string | number | null>>;
  attribution: Array<Record<string, string | number | null>>;
  contractTerms: Record<string, number>;
  methodology: Record<string, unknown>;
}

export interface AssetData {
  meta: Record<string, string | number>;
  energyAssets: Array<Record<string, string | number | null>>;
  agriculturalAssets: Array<Record<string, string | number | null>>;
  meters: Array<Record<string, string | number | null>>;
  topology: Array<Record<string, string>>;
}

export interface SystemStatusData {
  meta: Record<string, string | number>;
  currentUser: Record<string, string>;
  auth: Record<string, string | number>;
  accounts: Array<Record<string, string | number | boolean | null>>;
  roles: Array<Record<string, string>>;
  organizations: Array<Record<string, string>>;
  models: Array<Record<string, string>>;
  interfaces: Array<Record<string, string>>;
  alertRules: Array<Record<string, string>>;
  units: Array<Record<string, string>>;
  jobStatusCounts: Record<string, number>;
  jobs: Array<Record<string, string | number | null>>;
  auditEvents: Array<Record<string, string | number | null>>;
  components: Array<Record<string, string>>;
  backup: Record<string, string | number | null>;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: { userId: string; displayName: string; role: string };
}

async function requestJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const token = readSession()?.accessToken;
  const response = await fetch(`${API_BASE}${path}`, {
    signal,
    headers: { Accept: "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`接口请求失败（${response.status}）：${detail}`);
  }
  return response.json() as Promise<T>;
}

export const v2Api = {
  overview: (signal?: AbortSignal) => requestJson<OverviewData>("/api/v2/overview", signal),
  forecasts: (signal?: AbortSignal) => requestJson<ForecastCenterData>("/api/v2/forecasts", signal),
  strategies: (signal?: AbortSignal) => requestJson<StrategyData>("/api/v2/strategies", signal),
  parameters: (signal?: AbortSignal) => requestJson<ParametersData>("/api/v2/parameters", signal),
  stressTests: (signal?: AbortSignal) => requestJson<StressTestData>("/api/v2/stress-tests", signal),
  greenBenefits: (signal?: AbortSignal) => requestJson<GreenBenefitData>("/api/v2/green-direct-benefits", signal),
  assets: (signal?: AbortSignal) => requestJson<AssetData>("/api/v2/assets", signal),
  systemStatus: (signal?: AbortSignal) => requestJson<SystemStatusData>("/api/v2/system-status", signal),
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: "登录失败" })) as { detail?: string };
      throw new Error(payload.detail ?? "登录失败");
    }
    return response.json() as Promise<LoginResponse>;
  },
};
