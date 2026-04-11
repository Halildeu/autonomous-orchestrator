// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { PermissionProvider, ZanzibarGate } from '@mfe/auth';
import type { AuthzMeResponse } from '@mfe/auth';

/**
 * Zanzibar Pilot — mfe-reporting
 * Faz 1.5: ZanzibarGate ile rapor kartlarında object-level filtreleme.
 * Her rapor kartı ZanzibarGate(relation="can_view", objectType="report", objectId=route)
 * ile sarılır. Yetkisiz raporlar DOM'dan tamamen kaldırılır.
 */

/* ------------------------------------------------------------------ */
/*  Test fixtures                                                      */
/* ------------------------------------------------------------------ */

/** User with full REPORT module and specific report grants */
const fullAccessAuthz: AuthzMeResponse = {
  userId: '10',
  superAdmin: false,
  allowedModules: ['REPORT'],
  allowedCompanyIds: [1],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['ReportViewer'],
  modules: { REPORT: 'MANAGE' },
  actions: {},
  reports: {
    HR_REPORTS: 'ALLOW',
    FINANCE_REPORTS: 'ALLOW',
    AUDIT_REPORTS: 'ALLOW',
  },
  scopes: {},
  authzVersion: 1,
};

/** User with partial access — only HR_REPORTS granted */
const partialAccessAuthz: AuthzMeResponse = {
  userId: '20',
  superAdmin: false,
  allowedModules: ['REPORT'],
  allowedCompanyIds: [1],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['HRViewer'],
  modules: { REPORT: 'VIEW' },
  actions: {},
  reports: {
    HR_REPORTS: 'ALLOW',
    FINANCE_REPORTS: 'DENY',
  },
  scopes: {},
  authzVersion: 1,
};

/** SuperAdmin — sees everything */
const superAdminAuthz: AuthzMeResponse = {
  userId: '1',
  superAdmin: true,
  allowedModules: ['REPORT'],
  allowedCompanyIds: [],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['Admin'],
  modules: { REPORT: 'MANAGE' },
  actions: {},
  reports: {},
  scopes: {},
  authzVersion: 1,
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function createWrapper(authz: AuthzMeResponse) {
  const httpGet = vi.fn().mockResolvedValue({ data: authz });
  return ({ children }: { children: React.ReactNode }) => (
    <PermissionProvider httpGet={httpGet} initialData={authz}>
      {children}
    </PermissionProvider>
  );
}

/** Simulates the ReportingHub renderCard pattern with ZanzibarGate */
interface MockReportCard {
  route: string;
  title: string;
}

function ReportCardList({ reports }: { reports: MockReportCard[] }) {
  return (
    <div data-testid="report-list">
      {reports.map((report) => (
        <ZanzibarGate
          key={report.route}
          relation="can_view"
          objectType="report"
          objectId={report.route}
        >
          <div data-testid={`report-card-${report.route}`} role="button">
            <span>{report.title}</span>
          </div>
        </ZanzibarGate>
      ))}
    </div>
  );
}

const MOCK_REPORTS: MockReportCard[] = [
  { route: 'HR_REPORTS', title: 'Insan Kaynaklari Raporu' },
  { route: 'FINANCE_REPORTS', title: 'Finans Raporu' },
  { route: 'AUDIT_REPORTS', title: 'Denetim Raporu' },
];

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe('ZanzibarPilot — mfe-reporting', () => {
  it('shows all report cards when user has full access', () => {
    render(<ReportCardList reports={MOCK_REPORTS} />, {
      wrapper: createWrapper(fullAccessAuthz),
    });

    const list = screen.getByTestId('report-list');
    expect(within(list).getByTestId('report-card-HR_REPORTS')).toBeInTheDocument();
    expect(within(list).getByTestId('report-card-FINANCE_REPORTS')).toBeInTheDocument();
    expect(within(list).getByTestId('report-card-AUDIT_REPORTS')).toBeInTheDocument();
    expect(within(list).getAllByRole('button')).toHaveLength(3);
  });

  it('hides denied reports — user sees only HR, not FINANCE', () => {
    render(<ReportCardList reports={MOCK_REPORTS} />, {
      wrapper: createWrapper(partialAccessAuthz),
    });

    const list = screen.getByTestId('report-list');
    expect(within(list).getByTestId('report-card-HR_REPORTS')).toBeInTheDocument();
    expect(within(list).getByText('Insan Kaynaklari Raporu')).toBeInTheDocument();

    // FINANCE denied explicitly
    expect(within(list).queryByTestId('report-card-FINANCE_REPORTS')).not.toBeInTheDocument();
    expect(within(list).queryByText('Finans Raporu')).not.toBeInTheDocument();
  });

  it('superAdmin sees all report cards regardless of explicit grants', () => {
    render(<ReportCardList reports={MOCK_REPORTS} />, {
      wrapper: createWrapper(superAdminAuthz),
    });

    const list = screen.getByTestId('report-list');
    expect(within(list).getAllByRole('button')).toHaveLength(3);
    expect(within(list).getByText('Insan Kaynaklari Raporu')).toBeInTheDocument();
    expect(within(list).getByText('Finans Raporu')).toBeInTheDocument();
    expect(within(list).getByText('Denetim Raporu')).toBeInTheDocument();
  });

  it('report card is clickable when authorized', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();

    function ClickableReportCard() {
      return (
        <ZanzibarGate relation="can_view" objectType="report" objectId="HR_REPORTS">
          <button data-testid="hr-report-btn" onClick={handleClick}>
            HR Raporu
          </button>
        </ZanzibarGate>
      );
    }

    render(<ClickableReportCard />, {
      wrapper: createWrapper(fullAccessAuthz),
    });

    const btn = screen.getByTestId('hr-report-btn');
    expect(btn).toBeInTheDocument();
    await user.click(btn);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('denied report card is removed from DOM, click handler never fires', () => {
    const handleClick = vi.fn();

    function DeniedReportCard() {
      return (
        <ZanzibarGate relation="can_view" objectType="report" objectId="FINANCE_REPORTS">
          <button data-testid="finance-report-btn" onClick={handleClick}>
            Finans Raporu
          </button>
        </ZanzibarGate>
      );
    }

    render(<DeniedReportCard />, {
      wrapper: createWrapper(partialAccessAuthz),
    });

    expect(screen.queryByTestId('finance-report-btn')).not.toBeInTheDocument();
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('renders fallback UI for denied reports when fallback is provided', () => {
    function ReportWithFallback() {
      return (
        <ZanzibarGate
          relation="can_view"
          objectType="report"
          objectId="FINANCE_REPORTS"
          fallback={<div data-testid="access-fallback">Erisim yok</div>}
        >
          <div data-testid="finance-content">Finans Raporu</div>
        </ZanzibarGate>
      );
    }

    render(<ReportWithFallback />, {
      wrapper: createWrapper(partialAccessAuthz),
    });

    expect(screen.queryByTestId('finance-content')).not.toBeInTheDocument();
    expect(screen.getByTestId('access-fallback')).toBeInTheDocument();
    expect(screen.getByText('Erisim yok')).toBeInTheDocument();
  });
});
