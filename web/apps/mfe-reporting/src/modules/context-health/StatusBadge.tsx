import React from 'react';

type StatusBadgeProps = {
  status: string;
};

const toneMap: Record<string, { bg: string; text: string; dot: string }> = {
  OK: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  READY: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  PASS: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  WARN: { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500' },
  NOT_READY: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
  FAIL: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
  BLOCKED: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
  IDLE: { bg: 'bg-gray-50', text: 'text-gray-600', dot: 'bg-gray-400' },
  NOT_CONFIGURED: { bg: 'bg-gray-50', text: 'text-gray-600', dot: 'bg-gray-400' },
};

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const tone = toneMap[status] ?? toneMap.IDLE;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${tone.bg} ${tone.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
      {status}
    </span>
  );
};

export default StatusBadge;
