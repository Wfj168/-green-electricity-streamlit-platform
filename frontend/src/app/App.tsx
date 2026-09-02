import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { lazy, Suspense } from "react";
import { Spin } from "antd";
import { allPages } from "../config/navigation";
import { AppShell } from "../layout/AppShell";
import { readSession } from "../services/session";

const LoginPage = lazy(() => import("../pages/LoginPage").then((module) => ({ default: module.LoginPage })));
const OverviewPage = lazy(() => import("../pages/OverviewPage").then((module) => ({ default: module.OverviewPage })));
const WorkspacePage = lazy(() => import("../pages/WorkspacePage").then((module) => ({ default: module.WorkspacePage })));
const DomainDataPage = lazy(() => import("../pages/DomainDataPage").then((module) => ({ default: module.DomainDataPage })));
const AnalysisDataPage = lazy(() => import("../pages/AnalysisDataPage").then((module) => ({ default: module.AnalysisDataPage })));
const SystemStatusPage = lazy(() => import("../pages/SystemStatusPage").then((module) => ({ default: module.SystemStatusPage })));

const pageLoader = <div className="route-loader"><Spin size="large" tip="正在加载页面" /></div>;

function ProtectedApp() {
  const authRequired = import.meta.env.VITE_AUTH_REQUIRED === "true";
  return authRequired && !readSession() ? <Navigate to="/login" replace /> : <AppShell />;
}

export function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={pageLoader}><Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app" element={<ProtectedApp />}>
          <Route index element={<Navigate to="/app/overview" replace />} />
          <Route path="overview" element={<OverviewPage />} />
          {allPages.slice(1).map((page) => (
            <Route
              key={page.code}
              path={page.path.replace("/app/", "")}
              element={
                /^M0[2-5]-/.test(page.code)
                  ? <DomainDataPage page={page} />
                  : /^M(0[6-9]|10)-/.test(page.code)
                    ? <AnalysisDataPage page={page} />
                    : /^M11-/.test(page.code)
                      ? <SystemStatusPage page={page} />
                  : <WorkspacePage page={page} />
              }
            />
          ))}
        </Route>
        <Route path="/" element={<Navigate to="/app/overview" replace />} />
        <Route path="*" element={<Navigate to="/app/overview" replace />} />
      </Routes></Suspense>
    </BrowserRouter>
  );
}
