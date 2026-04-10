import React, { useMemo } from 'react';
import { cn } from '../utils/cn';
import {
  resolveAccessState,
  accessStyles,
  type AccessControlledProps,
} from '../internal/access-controller';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type MetricFormat = 'number' | 'currency' | 'percent';
export type MetricSize = 'sm' | 'md' | 'lg';

/** Props for the MetricComparisonCard component.
 * @example
 * ```tsx
 * <MetricComparisonCard title="Revenue" currentValue={125000} previousValue={100000} />
 * ```
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/metric-comparison-card)
 */
export interface MetricComparisonCardProps extends AccessControlledProps {
  /** Metric display label */
  title: string;
  /** Current period value */
  currentValue: number;
  /** Previous period value for comparison */
  previousValue: number;
  /** Number display format */
  format?: MetricFormat;
  /** Currency code for currency format */
  currencySymbol?: string;
  /** Period labels for current and previous */
  period?: { current: string; previous: string };
  /** Target value to show progress bar */
  target?: number;
  /** Data points for mini sparkline chart */
  sparklineData?: number[];
  /** Card size variant */
  size?: MetricSize;
  /** Invert trend colors (green for down, red for up) — useful for cost metrics */
  invertTrend?: boolean;
  /** Additional CSS class names for the root element */
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SIZE_CONFIG: Record<MetricSize, {
  valueFontSize: string;
  labelFontSize: string;
  badgeFontSize: string;
  padding: string;
  sparkHeight: number;
}> = {
  sm: { valueFontSize: 'text-xl', labelFontSize: 'text-xs', badgeFontSize: 'text-[10px]', padding: 'p-3', sparkHeight: 24 },
  md: { valueFontSize: 'text-3xl', labelFontSize: 'text-sm', badgeFontSize: 'text-xs', padding: 'p-4', sparkHeight: 32 },
  lg: { valueFontSize: 'text-4xl', labelFontSize: 'text-base', badgeFontSize: 'text-sm', padding: 'p-5', sparkHeight: 40 },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatMetricValue(value: number, format: MetricFormat, currency: string): string {
  switch (format) {
    case 'currency':
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(value);
    case 'percent':
      return `${value.toFixed(1)}%`;
    default:
      return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value);
  }
}

function computeChange(current: number, previous: number): { percent: number; direction: 'up' | 'down' | 'flat' } {
  if (previous === 0) return { percent: current === 0 ? 0 : 100, direction: current >= 0 ? 'up' : 'down' };
  const percent = ((current - previous) / Math.abs(previous)) * 100;
  const rounded = Math.round(percent * 10) / 10;
  if (rounded > 0) return { percent: rounded, direction: 'up' };
  if (rounded < 0) return { percent: Math.abs(rounded), direction: 'down' };
  return { percent: 0, direction: 'flat' };
}

// ---------------------------------------------------------------------------
// Sparkline SVG sub-component
// ---------------------------------------------------------------------------

interface SparklineProps {
  data: number[];
  height: number;
  color: string;
}

const Sparkline: React.FC<SparklineProps> = ({ data, height, color }) => {
  if (data.length < 2) return null;

  const width = 120;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 2;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - padding * 2) + padding;
    const y = height - ((v - min) / range) * (height - padding * 2) - padding;
    return `${x},${y}`;
  });

  const pathD = points.reduce((acc, pt, i) => (i === 0 ? `M ${pt}` : `${acc} L ${pt}`), '');

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="shrink-0"
      aria-hidden="true"
      role="img"
    >
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Last point dot */}
      {data.length > 0 && (
        <circle
          cx={parseFloat(points[points.length - 1].split(',')[0])}
          cy={parseFloat(points[points.length - 1].split(',')[1])}
          r="2.5"
          fill={color}
        />
      )}
    </svg>
  );
};

// ---------------------------------------------------------------------------
// Target progress bar sub-component
// ---------------------------------------------------------------------------

interface TargetBarProps {
  current: number;
  target: number;
  color: string;
}

const TargetBar: React.FC<TargetBarProps> = ({ current, target, color }) => {
  const percent = Math.min(100, Math.round((current / target) * 100));
  const isReached = current >= target;

  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-[10px] text-[var(--text-tertiary)] mb-1">
        <span>Target</span>
        <span className="font-mono">{percent}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-[var(--surface-muted)] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-(--motion-duration-slow)"
          style={{
            width: `${percent}%`,
            backgroundColor: isReached ? 'var(--state-success-text)' : color,
          }}
        />
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/** Period-over-period metric comparison card with trend indicator, sparkline, and target progress. */
export function MetricComparisonCard({
  title,
  currentValue,
  previousValue,
  format = 'number',
  currencySymbol = 'USD',
  period,
  target,
  sparklineData,
  size = 'md',
  invertTrend = false,
  className,
  access,
  accessReason,
}: MetricComparisonCardProps) {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null;

  const s = SIZE_CONFIG[size];
  const change = useMemo(() => computeChange(currentValue, previousValue), [currentValue, previousValue]);

  // Determine trend color
  const isPositive = useMemo(() => {
    if (change.direction === 'flat') return true;
    return invertTrend ? change.direction === 'down' : change.direction === 'up';
  }, [change.direction, invertTrend]);

  const trendColor = isPositive
    ? 'var(--state-success-text)'
    : 'var(--state-error-text)';

  const trendBg = isPositive
    ? 'var(--state-success-bg)'
    : 'var(--state-error-bg)';

  const trendIcon = change.direction === 'up' ? '\u2191' : change.direction === 'down' ? '\u2193' : '\u2192';
  const accentColor = isPositive ? 'var(--state-success-text)' : 'var(--state-error-text)';

  return (
    <div
      className={cn(
        'border border-border-default rounded-lg bg-surface-default overflow-hidden',
        s.padding,
        accessStyles(accessState.state),
        className,
      )}
      data-component="metric-comparison-card"
      data-access-state={accessState.state}
      role="group"
      aria-label={`${title} metric`}
      {...(accessState.isDisabled ? { 'aria-disabled': true } : {})}
      {...(accessReason ? { title: accessReason } : {})}
    >
      {/* Header: Label + sparkline */}
      <div className="flex items-start justify-between mb-1">
        <span className={cn(s.labelFontSize, 'font-medium text-[var(--text-secondary)]')}>
          {title}
        </span>
        {sparklineData && sparklineData.length >= 2 && (
          <Sparkline data={sparklineData} height={s.sparkHeight} color={accentColor} />
        )}
      </div>

      {/* Current value */}
      <div className="flex items-end gap-3 mb-1">
        <span className={cn(s.valueFontSize, 'font-bold text-[var(--text-primary)] leading-none font-mono')}>
          {formatMetricValue(currentValue, format, currencySymbol)}
        </span>

        {/* Change badge */}
        <span
          className={cn(
            'inline-flex items-center gap-0.5 rounded-full font-medium px-2 py-0.5',
            s.badgeFontSize,
          )}
          style={{ backgroundColor: trendBg, color: trendColor }}
          aria-label={`${change.direction === 'up' ? 'increased' : change.direction === 'down' ? 'decreased' : 'unchanged'} by ${change.percent}%`}
        >
          <span>{trendIcon}</span>
          <span className="font-mono">{change.percent}%</span>
        </span>
      </div>

      {/* Previous value */}
      <div className="flex items-center gap-2">
        <span className={cn('text-[var(--text-tertiary)] font-mono', s.badgeFontSize)}>
          Previous: {formatMetricValue(previousValue, format, currencySymbol)}
        </span>
      </div>

      {/* Period labels */}
      {period && (
        <div className="flex items-center gap-3 mt-1 text-[10px] text-[var(--text-tertiary)]">
          <span>{period.current}</span>
          <span>vs</span>
          <span>{period.previous}</span>
        </div>
      )}

      {/* Target progress bar */}
      {target != null && target > 0 && (
        <TargetBar current={currentValue} target={target} color={accentColor} />
      )}
    </div>
  );
}

MetricComparisonCard.displayName = 'MetricComparisonCard';
export default MetricComparisonCard;
