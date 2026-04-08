import React, { Suspense, useMemo } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAppSelector } from "../store/store.hooks";
import { isPermitAllMode } from "../auth/auth-config";
import { ProtectedRoute } from "../guards/ProtectedRoute";
import {
  isEthicRemoteEnabled,
  isSuggestionsRemoteEnabled,
} from "../shell-navigation";
import { useShellCommonI18n } from "../i18n";
import {
  SuggestionsApp,
  EthicApp,
  AccessModule,
  AuditModule,
  UsersModule,
  SchemaExplorerModule,
} from "./lazy-routes";
import { ReportingLayout } from "../../pages/admin/reports/ReportingLayout";
const ReportBuilderWizard = React.lazy(() => import("../../pages/admin/reports/builder/ReportBuilderWizard").then(m => ({ default: m.ReportBuilderWizard })));
const DashboardBuilder = React.lazy(() => import("../../pages/admin/reports/dashboard-builder/DashboardBuilder").then(m => ({ default: m.DashboardBuilder })));
const ReportEditorRoute = React.lazy(() => import("../../pages/admin/reports/builder/ReportEditor").then(m => ({ default: m.ReportEditorRoute })));

/* ---- Page imports ---- */
import { LoginPage } from "../../pages/login";
import { RegisterPage } from "../../pages/register";
import { UnauthorizedPage } from "../../pages/unauthorized";
import ThemeMatrixPage from "../../pages/runtime/ThemeMatrixPage";
import { HomePage } from "../../pages/home/HomePage";
import ThemeAdminPage from "../../pages/admin/ThemeAdminPage";
import DesignLabPage from "../../pages/admin/DesignLabPage";
import { DesignLabRoutes } from "../../pages/admin/design-lab/DesignLabRoutes";

const XSuiteDashboardPage = React.lazy(
  () => import("../../pages/admin/XSuiteDashboardPage"),
);
const ServiceControlPage = React.lazy(
  () => import("../../pages/admin/service-control/ServiceControlPage"),
);

/* ------------------------------------------------------------------ */
/*  AppRouter — All application routes                                 */
/* ------------------------------------------------------------------ */

const AuthTraceRoute: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  // Dev-only auth state logging
  return <>{children}</>;
};

export const AppRouter: React.FC = () => {
  const { t } = useShellCommonI18n();
  const authState = useAppSelector((state) => state.auth);
  const { token, initialized } = authState;
  const permitAllMode = isPermitAllMode();
  const suggestionsEnabled = isSuggestionsRemoteEnabled();
  const ethicEnabled = isEthicRemoteEnabled();

  const defaultShellPath = '/home';

  return (
    <Suspense fallback={<div>{t("shell.header.suspenseLoading")}</div>}>
      <Routes>
        <Route
          path="/suggestions"
          element={
            suggestionsEnabled ? (
              <ProtectedRoute>
                <SuggestionsApp />
              </ProtectedRoute>
            ) : (
              <Navigate to={defaultShellPath} replace />
            )
          }
        />
        <Route
          path="/ethic"
          element={
            ethicEnabled ? (
              <ProtectedRoute>
                <EthicApp />
              </ProtectedRoute>
            ) : (
              <Navigate to={defaultShellPath} replace />
            )
          }
        />
        <Route
          path="/access/roles"
          element={
            <ProtectedRoute requiredModule="ACCESS">
              <AccessModule />
            </ProtectedRoute>
          }
        />
        <Route path="/access" element={<Navigate to="/access/roles" replace />} />
        <Route
          path="/audit/events"
          element={
            <ProtectedRoute requiredModule="AUDIT">
              <AuditModule />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/reports/builder"
          element={
            <ProtectedRoute requiredModule="REPORT">
              <Suspense fallback={<div className="flex justify-center py-16"><span className="inline-flex h-6 w-6 animate-spin rounded-full border-2 border-border-subtle border-t-action-primary" /></div>}>
                <ReportBuilderWizard />
              </Suspense>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/reports/builder/dashboard"
          element={
            <ProtectedRoute requiredModule="REPORT">
              <Suspense fallback={<div className="flex justify-center py-16"><span className="inline-flex h-6 w-6 animate-spin rounded-full border-2 border-border-subtle border-t-action-primary" /></div>}>
                <DashboardBuilder />
              </Suspense>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/reports/builder/edit/:reportKey"
          element={
            <ProtectedRoute requiredModule="REPORT">
              <Suspense fallback={<div className="flex justify-center py-16"><span className="inline-flex h-6 w-6 animate-spin rounded-full border-2 border-border-subtle border-t-action-primary" /></div>}>
                <ReportEditorRoute />
              </Suspense>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/reports/*"
          element={
            <ProtectedRoute requiredModule="REPORT">
              <ReportingLayout />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/reports"
          element={
            <ProtectedRoute requiredModule="REPORT">
              <ReportingLayout />
            </ProtectedRoute>
          }
        />
        <Route path="/reports/*" element={<Navigate to="/admin/reports" replace />} />
        <Route path="/reports" element={<Navigate to="/admin/reports" replace />} />
        <Route
          path="/admin/users"
          element={
            <AuthTraceRoute>
              <ProtectedRoute
                requiredModule="USER_MANAGEMENT"
              >
                <UsersModule />
              </ProtectedRoute>
            </AuthTraceRoute>
          }
        />
        <Route
          path="/admin/schema-explorer/*"
          element={
            <ProtectedRoute requiredModule="THEME">
              <SchemaExplorerModule />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/themes"
          element={
            <ProtectedRoute requiredModule="THEME">
              <ThemeAdminPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/design-lab/*"
          element={
            <ProtectedRoute requiredModule="THEME">
              <DesignLabRoutes />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/design-lab-legacy"
          element={
            <ProtectedRoute requiredModule="THEME">
              <DesignLabPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/x-suite-dashboard"
          element={
            <ProtectedRoute requiredModule="THEME">
              <XSuiteDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/services"
          element={
            <ProtectedRoute requiredModule="THEME">
              <ServiceControlPage />
            </ProtectedRoute>
          }
        />
        <Route path="/home" element={<HomePage />} />
        <Route path="/runtime/theme-matrix" element={<ThemeMatrixPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        <Route
          path="/"
          element={
            !initialized && !permitAllMode ? (
              <div className="px-6 py-10 text-sm font-medium text-text-secondary">
                {t("auth.session.validating")}
              </div>
            ) : (
              <Navigate
                to={token || permitAllMode ? defaultShellPath : "/login"}
                replace
              />
            )
          }
        />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Suspense>
  );
};
