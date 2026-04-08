import {
  buildAuditSummarySnapshot,
  getAuditFeedCapability,
  listAuditSummaryGroups,
  type AuditCapabilitySummarySnapshot,
  type AuditSummarySnapshot,
} from '@platform/capabilities';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAppDispatch, useAppSelector } from '../store/store.hooks';
import { fetchAuditSummaryEvents } from '../../features/audit/lib/audit-summary-api';
import { collectAuditSummaryNotifications } from '../../features/audit/lib/audit-summary-notifications';
import { MODULE_KEYS } from '../../features/auth/lib/permissions.constants';
import { usePermissions } from '@mfe/auth';
import { pushNotification, toggleOpen } from '../../features/notifications/model/notifications.slice';

type AuditSummaryStripStatus = 'idle' | 'loading' | 'ready' | 'blocked' | 'error';

type AuditSummaryStripState = {
  status: AuditSummaryStripStatus;
  groups: AuditSummarySnapshot[];
  error: string | null;
  gateReason: string;
  lastFetchedAt: string | null;
};

const summaryGroups = listAuditSummaryGroups();
const initialGroups = summaryGroups.map((group) => buildAuditSummarySnapshot(group.id, []));

const initialState: AuditSummaryStripState = {
  status: 'idle',
  groups: initialGroups,
  error: null,
  gateReason: 'Audit özeti için giriş yapın.',
  lastFetchedAt: null,
};

const AUDIT_SUMMARY_POLL_MS = 45_000;

const formatAuditTimestamp = (value: string | null): string => {
  if (!value) {
    return 'n/a';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'n/a';
  }

  return new Intl.DateTimeFormat('tr-TR', {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: 'short',
  }).format(parsed);
};

const getAuditSummaryErrorMessage = (error: unknown): string => {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return 'Audit özeti alınamadı.';
};

const resolveLatestTimestamp = (
  snapshots: readonly { id: string; timestamp: string }[],
): { id: string; timestamp: string } | null => {
  let current: { id: string; timestamp: string } | null = null;

  for (const snapshot of snapshots) {
    if (!current || Date.parse(snapshot.timestamp) > Date.parse(current.timestamp)) {
      current = snapshot;
    }
  }

  return current;
};

const loadAuditSummaryGroups = async (email: string): Promise<AuditSummarySnapshot[]> => {
  const seenCapabilityIds = new Set<string>();
  const capabilityIds = summaryGroups.flatMap((group) =>
    group.capabilityIds.filter((capabilityId) => {
      if (seenCapabilityIds.has(capabilityId)) {
        return false;
      }
      seenCapabilityIds.add(capabilityId);
      return true;
    }),
  );

  const capabilitySnapshots = await Promise.all(
    capabilityIds.map(async (capabilityId): Promise<AuditCapabilitySummarySnapshot> => {
      const capability = getAuditFeedCapability(capabilityId);
      const response = await fetchAuditSummaryEvents({
        action: capability.action,
        page: 0,
        pageSize: 3,
        service: capability.service,
        user: email,
      });
      const latestEvent = resolveLatestTimestamp(
        response.events.map((event) => ({
          id: event.id,
          timestamp: event.timestamp,
        })),
      );

      return {
        capabilityId,
        total: Number(response.total ?? 0),
        latestEventId: latestEvent?.id ?? null,
        latestEventTimestamp: latestEvent?.timestamp ?? null,
        latestAction: capability.action,
      };
    }),
  );

  return summaryGroups.map((group) => buildAuditSummarySnapshot(group.id, capabilitySnapshots));
};

export const AuditSummaryStrip: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { token, user } = useAppSelector((state) => state.auth);
  const { hasModule, isSuperAdmin } = usePermissions();
  const [state, setState] = useState<AuditSummaryStripState>(initialState);
  const previousGroupsRef = useRef<AuditSummarySnapshot[] | null>(null);
  const normalizedEmail = useMemo(() => user?.email?.trim() ?? '', [user?.email]);
  const canReadAudit = Boolean(token) && Boolean(normalizedEmail) && (isSuperAdmin() || hasModule(MODULE_KEYS.AUDIT));

  const refresh = useCallback(async () => {
    if (!canReadAudit || !normalizedEmail) {
      setState({
        ...initialState,
        status: 'blocked',
        gateReason: token ? 'Audit-read yetkisi olmadan özet kartları fail-closed kalır.' : 'Audit özeti için giriş yapın.',
      });
      return;
    }

    setState((current) => ({
      ...current,
      status: 'loading',
      error: null,
    }));

    try {
      const groups = await loadAuditSummaryGroups(normalizedEmail);
      setState({
        status: 'ready',
        groups,
        error: null,
        gateReason: 'Audit özeti aktif. Ayrıntılı filtreler için audit ekranını açabilirsiniz.',
        lastFetchedAt: new Date().toISOString(),
      });
    } catch (error: unknown) {
      setState({
        ...initialState,
        status: 'error',
        error: getAuditSummaryErrorMessage(error),
        gateReason: 'Audit özet verisi alınırken hata oluştu.',
      });
    }
  }, [canReadAudit, normalizedEmail, token]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!token) {
      previousGroupsRef.current = null;
      return;
    }

    if (state.status !== 'ready') {
      return;
    }

    const previousGroups = previousGroupsRef.current;
    previousGroupsRef.current = state.groups;

    if (!previousGroups || !normalizedEmail) {
      return;
    }

    const notifications = collectAuditSummaryNotifications({
      email: normalizedEmail,
      previousGroups,
      nextGroups: state.groups,
    });

    if (notifications.length === 0) {
      return;
    }

    notifications.forEach((notification) => {
      dispatch(
        pushNotification({
          id: notification.id,
          message: notification.message,
          description: notification.description,
          type: notification.type,
          priority: notification.priority,
          meta: {
            source: notification.source,
            open: notification.open,
            pathname: notification.pathname,
            search: notification.search,
            actionLabel: notification.actionLabel,
          },
        }),
      );
    });

    if (notifications.some((notification) => notification.open)) {
      dispatch(toggleOpen(true));
    }
  }, [dispatch, normalizedEmail, state.groups, state.status, token]);

  useEffect(() => {
    if (!canReadAudit || typeof window === 'undefined') {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refresh();
    }, AUDIT_SUMMARY_POLL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [canReadAudit, refresh]);

  if (!token) {
    return null;
  }

  return (
    <section className="border-b border-border-subtle bg-surface-panel/70 px-8 py-4" data-testid="audit-summary-strip">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-col gap-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">Audit özeti</p>
            <p className="text-sm text-text-primary">
              Shared capability catalog, oturum ve replay görünürlüğünü audit ekranına girmeden özetliyor.
            </p>
            <p className="text-xs text-text-secondary">
              {state.gateReason}
              {state.lastFetchedAt ? ` Son yenileme: ${formatAuditTimestamp(state.lastFetchedAt)}.` : ''}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="inline-flex items-center rounded-full border border-border-subtle bg-surface-default px-3 py-1.5 text-xs font-semibold text-text-primary transition hover:bg-surface-muted disabled:text-text-secondary"
              onClick={() => {
                void refresh();
              }}
              disabled={!canReadAudit || state.status === 'loading'}
            >
              {state.status === 'loading' ? 'Özet yenileniyor...' : 'Özeti yenile'}
            </button>
            <button
              type="button"
              className="inline-flex items-center rounded-full border border-action-primary-border bg-action-primary px-3 py-1.5 text-xs font-semibold text-action-primary-text shadow-xs transition hover:opacity-90 disabled:opacity-60"
              onClick={() => navigate('/audit/events')}
              disabled={!canReadAudit}
            >
              Audit ekranını aç
            </button>
          </div>
        </div>

        {state.error ? (
          <div className="rounded-2xl border border-state-danger-border bg-state-danger-bg px-4 py-3 text-xs text-state-danger-text">
            {state.error}
          </div>
        ) : null}

        <div className="grid gap-3 xl:grid-cols-3">
          {state.groups.map((group) => (
            <article
              key={group.groupId}
              className="rounded-2xl border border-border-subtle bg-surface-default px-4 py-3 shadow-xs"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <h3 className="text-sm font-semibold text-text-primary">{group.title}</h3>
                  <p className="text-xs leading-5 text-text-secondary">{group.description}</p>
                </div>
                <span className="rounded-full bg-surface-muted px-2.5 py-1 text-[11px] font-semibold text-text-primary">
                  {group.total} olay
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {group.metrics.map((metric) => (
                  <span
                    key={`${group.groupId}-${metric.capabilityId}`}
                    className="rounded-full border border-border-subtle bg-surface-panel px-2.5 py-1 text-[11px] font-semibold text-text-secondary"
                  >
                    {metric.label}: {metric.total}
                  </span>
                ))}
              </div>
              <p className="mt-3 text-xs text-text-secondary">
                Son olay: {formatAuditTimestamp(group.latestEventTimestamp)}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
};

export default AuditSummaryStrip;
