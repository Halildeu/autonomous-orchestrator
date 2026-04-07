import React from 'react';
import { cn } from '../utils/cn';
import {
  resolveAccessState,
  accessStyles,
  type AccessControlledProps,
} from '../internal/access-controller';
import { formatValue, getToneClasses, type EnterpriseTone, type FormatOptions } from './types';

// ── Types ──

export interface AgingBucket {
  id: string;
  label: string;
  count: number;
  value: number;
  tone?: EnterpriseTone;
}

/** Displays aging analysis with bucket cards, optional stacked bar, and totals.
 * @example
 * ```tsx
 * <AgingBuckets />
 * ```
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/aging-buckets)
 */
export interface AgingBucketsProps extends AccessControlledProps {
  /** Aging bucket data items to display */
  buckets: AgingBucket[];
  /** Layout direction of the bucket cards */
  orientation?: 'horizontal' | 'vertical';
  /** Show a stacked percentage bar above the bucket cards */
  showStackedBar?: boolean;
  /** Number formatting options (currency, decimal places, etc.) */
  formatOptions?: FormatOptions;
  /** Called when a bucket card or bar segment is clicked */
  onBucketClick?: (bucket: AgingBucket) => void;
  /** Additional CSS class names for the root element */
  className?: string;
}

// ── Default tone assignment based on bucket index ──

function defaultTone(index: number, total: number): EnterpriseTone {
  if (total <= 1) return 'default';
  const ratio = index / (total - 1);
  if (ratio <= 0.25) return 'success';
  if (ratio <= 0.5) return 'info';
  if (ratio <= 0.75) return 'warning';
  return 'danger';
}

// ── Component ──

/** Displays aging analysis with bucket cards, optional stacked bar, and totals. */
export const AgingBuckets: React.FC<AgingBucketsProps> = ({
  buckets,
  orientation = 'horizontal',
  showStackedBar = false,
  formatOptions = {},
  onBucketClick,
  className,
  access,
  accessReason,
}) => {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null;

  const totalValue = buckets.reduce((sum, b) => sum + b.value, 0);
  const totalCount = buckets.reduce((sum, b) => sum + b.count, 0);

  const getPercentage = (value: number): number => {
    if (totalValue === 0) return 0;
    return Math.round((value / totalValue) * 1000) / 10;
  };

  const toneColorMap: Record<EnterpriseTone, string> = {
    default: 'var(--text-secondary)',
    success: 'var(--state-success-text)',
    warning: 'var(--state-warning-text)',
    danger: 'var(--state-error-text)',
    info: 'var(--state-info-text)',
  };

  const isHorizontal = orientation === 'horizontal';

  return (
    <div
      className={cn(
        'border border-border-default rounded-lg bg-surface-default p-4',
        accessStyles(accessState.state),
        className,
      )}
      data-component="aging-buckets"
      data-access-state={accessState.state}
      title={accessReason}
    >
      {/* Stacked bar */}
      {showStackedBar && (
        <div className="mb-4 flex h-6 w-full overflow-hidden rounded-md">
          {buckets.map((bucket, i) => {
            const pct = getPercentage(bucket.value);
            const tone = bucket.tone ?? defaultTone(i, buckets.length);
            if (pct === 0) return null;
            return (
              <div
                key={bucket.id}
                role={onBucketClick ? 'button' : undefined}
                tabIndex={onBucketClick ? 0 : undefined}
                className={cn('h-full transition-all duration-300 first:rounded-l-md last:rounded-r-md', onBucketClick && 'cursor-pointer hover:opacity-80 focus-visible:ring-2 focus-visible:ring-focus-outline')}
                style={{ width: `${pct}%`, backgroundColor: toneColorMap[tone] }}
                onClick={() => onBucketClick?.(bucket)}
                onKeyDown={(e) => {
                  if ((e.key === 'Enter' || e.key === ' ') && onBucketClick) {
                    e.preventDefault();
                    onBucketClick(bucket);
                  }
                }}
                title={`${bucket.label}: ${pct}%`}
              >
                {pct > 8 && (
                  <span className="flex h-full items-center justify-center text-[10px] font-bold text-text-inverse">
                    {pct}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Bucket cards */}
      <div className={cn('gap-3', isHorizontal ? 'flex flex-wrap' : 'flex flex-col')}>
        {buckets.map((bucket, i) => {
          const tone = bucket.tone ?? defaultTone(i, buckets.length);
          const toneClasses = getToneClasses(tone);
          const pct = getPercentage(bucket.value);

          return (
            <div
              key={bucket.id}
              role={onBucketClick ? 'button' : undefined}
              tabIndex={onBucketClick ? 0 : undefined}
              className={cn(
                'flex-1 min-w-[120px] rounded-lg border p-3 transition-all duration-200',
                toneClasses.border,
                toneClasses.bg,
                onBucketClick && 'cursor-pointer hover:shadow-md hover:scale-[1.02] focus-visible:ring-2 focus-visible:ring-focus-outline',
              )}
              onClick={() => onBucketClick?.(bucket)}
              onKeyDown={(e) => {
                if ((e.key === 'Enter' || e.key === ' ') && onBucketClick) {
                  e.preventDefault();
                  onBucketClick(bucket);
                }
              }}
              aria-label={bucket.label}
            >
              {/* Label */}
              <div className="text-xs font-medium text-text-secondary mb-1">
                {bucket.label}
              </div>

              {/* Value */}
              <div className={cn('text-lg font-bold', toneClasses.text)}>
                {formatValue(bucket.value, formatOptions)}
              </div>

              {/* Count & Percentage */}
              <div className="mt-1 flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
                <span>{bucket.count} items</span>
                <span className="text-border-default">{'\u00B7'}</span>
                <span>{pct}%</span>
              </div>

              {/* Mini bar */}
              <div className="mt-2 h-1 w-full rounded-full bg-surface-muted overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: toneColorMap[tone] }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Total row */}
      <div className="mt-3 flex items-center justify-between border-t border-border-subtle pt-3">
        <span className="text-sm font-semibold text-text-primary">Total</span>
        <div className="flex items-center gap-4">
          <span className="text-xs text-[var(--text-tertiary)]">{totalCount} items</span>
          <span className="text-sm font-bold text-text-primary">
            {formatValue(totalValue, formatOptions)}
          </span>
        </div>
      </div>
    </div>
  );
};

AgingBuckets.displayName = 'AgingBuckets';
export default AgingBuckets;
