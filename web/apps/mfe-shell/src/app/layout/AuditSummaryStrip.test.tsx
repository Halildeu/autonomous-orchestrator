// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuditSummaryStrip } from './AuditSummaryStrip';

const navigateMock = vi.fn();
const fetchAuditEventsMock = vi.fn();
const dispatchMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock('../store/store.hooks', () => ({
  useAppDispatch: () => dispatchMock,
  useAppSelector: (selector: (state: { auth: { token: string | null; user: { email: string | null } | null } }) => unknown) =>
    selector({
      auth: {
        token: 'demo-token',
        user: { email: 'admin@example.com' },
      },
    }),
}));

vi.mock('@mfe/auth', () => ({
  usePermissions: () => ({
    hasModule: () => true,
    isSuperAdmin: () => false,
  }),
}));

vi.mock('../../features/audit/lib/audit-summary-api', () => ({
  fetchAuditSummaryEvents: (...args: unknown[]) => fetchAuditEventsMock(...args),
}));

describe('AuditSummaryStrip', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    navigateMock.mockReset();
    fetchAuditEventsMock.mockReset();
    dispatchMock.mockReset();
    fetchAuditEventsMock.mockImplementation(async ({ action }: { action?: string }) => {
      if (action === 'SESSION_CREATED') {
        return {
          events: [{ id: 'audit-1', timestamp: '2026-03-14T10:00:00Z' }],
          total: 4,
          page: 0,
        };
      }
      if (action === 'USER_SESSION_TIMEOUT_SYNCED') {
        return {
          events: [{ id: 'audit-2', timestamp: '2026-03-14T11:00:00Z' }],
          total: 3,
          page: 0,
        };
      }
      if (action === 'USER_SESSION_TIMEOUT_SYNC_CONFLICT') {
        return {
          events: [{ id: 'audit-3', timestamp: '2026-03-14T09:00:00Z' }],
          total: 1,
          page: 0,
        };
      }
      if (action === 'USER_NOTIFICATION_PREFERENCE_SYNCED') {
        return {
          events: [{ id: 'audit-4', timestamp: '2026-03-14T12:00:00Z' }],
          total: 2,
          page: 0,
        };
      }
      return {
        events: [{ id: 'audit-5', timestamp: '2026-03-14T08:00:00Z' }],
        total: 1,
        page: 0,
      };
    });
  });

  it('shared capability catalog ile grup özetlerini render eder', async () => {
    render(<AuditSummaryStrip />);

    await waitFor(() => {
      expect(screen.getByText('Session bootstrap')).toBeInTheDocument();
    });

    expect(screen.getByText('Replay success: 3')).toBeInTheDocument();
    expect(screen.getByText('Replay conflict: 1')).toBeInTheDocument();
    expect(screen.getByText('Preference success: 2')).toBeInTheDocument();
    expect(screen.getByText('Preference conflict: 1')).toBeInTheDocument();
  });

  it('audit ekranını aç düğmesi route değiştirir', async () => {
    render(<AuditSummaryStrip />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Audit ekranını aç' })[0]).toBeEnabled();
    });

    fireEvent.click(screen.getAllByRole('button', { name: 'Audit ekranını aç' })[0]);

    expect(navigateMock).toHaveBeenCalledWith('/audit/events');
  });
});
