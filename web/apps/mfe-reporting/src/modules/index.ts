import { listSharedReportsForChannel } from '@platform/capabilities';
import type { ReportModule } from './types';
import { usersReportModule } from './users-report';
import { accessReportModule } from './access-report';
import { auditReportModule } from './audit-report';
import { hrDemographicReportModule } from './hr-demographic-report';
import { monthlyLoginModule } from './monthly-login-summary';
import { weeklyAuditDigestModule } from './weekly-audit-digest';
import { hrCompensationModule } from './hr-compensation-report';
import { hrExecutiveSummaryModule } from './hr-executive-summary';
import { contextHealthModule } from './context-health';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyReportModule = ReportModule<any, any>;
const reportModuleMap = new Map<string, AnyReportModule>([
  [usersReportModule.id, usersReportModule as AnyReportModule],
  [accessReportModule.id, accessReportModule as AnyReportModule],
  [auditReportModule.id, auditReportModule as AnyReportModule],
  [hrDemographicReportModule.id, hrDemographicReportModule as AnyReportModule],
  [monthlyLoginModule.id, monthlyLoginModule as AnyReportModule],
  [weeklyAuditDigestModule.id, weeklyAuditDigestModule as AnyReportModule],
  [hrCompensationModule.id, hrCompensationModule as AnyReportModule],
  [hrExecutiveSummaryModule.id, hrExecutiveSummaryModule as AnyReportModule],
  [contextHealthModule.id, contextHealthModule as AnyReportModule],
]);

const catalogModules = listSharedReportsForChannel('web')
  .map((report) => reportModuleMap.get(report.webModuleId))
  .filter(
    (
      module,
    ): module is Exclude<ReturnType<typeof reportModuleMap.get>, undefined> => Boolean(module),
  );

// Include modules that are registered but not yet in the catalog (e.g., new dashboards)
const catalogIds = new Set(catalogModules.map((m) => m.id));
const extraModules = [...reportModuleMap.values()].filter((m) => !catalogIds.has(m.id));

export const reportModules = [...catalogModules, ...extraModules];

export type { ReportModule } from './types';
