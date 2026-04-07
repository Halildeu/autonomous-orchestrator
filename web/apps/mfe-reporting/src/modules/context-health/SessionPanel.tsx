import React from 'react';
import StatusBadge from './StatusBadge';

type Props = {
  session: Record<string, unknown> | null;
};

type InfoRowProps = {
  label: string;
  value: React.ReactNode;
};

const InfoRow: React.FC<InfoRowProps> = ({ label, value }) => (
  <div className="flex items-center justify-between border-b border-border-subtle py-2 last:border-b-0">
    <span className="text-xs text-text-subtle">{label}</span>
    <span className="text-xs font-medium text-text-primary">{value}</span>
  </div>
);

const SessionPanel: React.FC<Props> = ({ session }) => {
  if (!session || !session.available) {
    return (
      <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
        <h3 className="mb-2 text-sm font-semibold text-text-primary">Active Session</h3>
        <p className="text-xs text-text-subtle">Session data not available</p>
      </div>
    );
  }

  const formatTtl = (seconds: unknown): string => {
    const s = Number(seconds) || 0;
    if (s >= 86400) return `${Math.floor(s / 86400)}d`;
    if (s >= 3600) return `${Math.floor(s / 3600)}h`;
    return `${Math.floor(s / 60)}m`;
  };

  const formatDate = (iso: unknown): string => {
    if (!iso || typeof iso !== 'string') return '—';
    try {
      return new Date(iso).toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' });
    } catch {
      return String(iso).substring(0, 19);
    }
  };

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-primary p-4 shadow-xs">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">Active Session</h3>
        <StatusBadge status={String(session.overallStatus ?? 'UNKNOWN')} />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Column 1: Session Info */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-subtle">Session</p>
          <InfoRow label="ID" value={String(session.sessionId ?? '—')} />
          <InfoRow label="Status" value={<StatusBadge status={String(session.sessionStatus ?? '—')} />} />
          <InfoRow label="Context Hash" value={<code className="text-[10px] text-text-subtle">{String(session.contextHash ?? '—')}</code>} />
          <InfoRow label="TTL" value={formatTtl(session.ttlSeconds)} />
          <InfoRow label="Expires" value={formatDate(session.expiresAt)} />
          <InfoRow label="Last Update" value={formatDate(session.generatedAt)} />
        </div>

        {/* Column 2: System State */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-subtle">System</p>
          <InfoRow label="Readiness" value={<StatusBadge status={String(session.readinessStatus ?? '—')} />} />
          <InfoRow label="Fails / Warns" value={`${session.readinessFails ?? 0} / ${session.readinessWarns ?? 0}`} />
          <InfoRow label="Core Lock" value={<StatusBadge status={String(session.coreLockStatus ?? '—')} />} />
          <InfoRow label="Write Mode" value={String(session.coreWriteMode ?? '—')} />
          <InfoRow label="Git Clean" value={session.gitClean ? 'Yes' : 'No'} />
          <InfoRow label="Dirty Files" value={String(session.dirtyFilesCount ?? 0)} />
        </div>

        {/* Column 3: Runtime */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-subtle">Runtime</p>
          <InfoRow label="Network" value={session.networkEnabled ? 'Enabled' : 'Disabled'} />
          <InfoRow label="AIRunner" value={<StatusBadge status={String(session.airunnerStatus ?? 'IDLE')} />} />
          <InfoRow label="AIRunner Mode" value={String(session.airunnerMode ?? '—')} />
          <InfoRow label="Doer Loop" value={String(session.doerLoopState ?? 'MISSING')} />
          <InfoRow label="Targets" value={String(session.targetCount ?? 0)} />
          <InfoRow label="Repos" value={String(session.repoCount ?? 0)} />
          <InfoRow label="Providers" value={`${session.providerCount ?? 0} (${session.capabilityCount ?? 0} cap)`} />
          <InfoRow label="Handoffs" value={`${session.handoffCount ?? 0} / ${session.closeoutCount ?? 0} closeout`} />
        </div>
      </div>
    </div>
  );
};

export default SessionPanel;
