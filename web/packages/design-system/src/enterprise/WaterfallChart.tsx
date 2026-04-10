import React, { useMemo, useState, useCallback } from 'react';
import { cn } from '../utils/cn';
import {
  resolveAccessState,
  accessStyles,
  type AccessControlledProps,
} from '../internal/access-controller';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A single item in the waterfall chart.
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/waterfall-chart)
 */
export interface WaterfallItem {
  /** Unique identifier */
  id: string;
  /** Display label */
  label: string;
  /** Numeric value (positive for increases, negative for decreases) */
  value: number;
  /** Bar type: increase (green), decrease (red), or total (blue) */
  type: 'increase' | 'decrease' | 'total';
  /** Optional custom bar color override */
  color?: string;
}

/**
 * Props for the WaterfallChart component.
 *
 * @example
 * ```tsx
 * <WaterfallChart
 *   items={[
 *     { id: 'rev', label: 'Revenue', value: 1000, type: 'increase' },
 *     { id: 'cogs', label: 'COGS', value: -400, type: 'decrease' },
 *     { id: 'gp', label: 'Gross Profit', value: 600, type: 'total' },
 *   ]}
 * />
 * ```
 */
export interface WaterfallChartProps extends AccessControlledProps {
  /** Array of waterfall items to render */
  items: WaterfallItem[];
  /** Chart height (number for px, string for CSS value) */
  height?: number | string;
  /** Show numeric values above/below bars */
  showValues?: boolean;
  /** Show dashed connector lines between bars */
  showConnectors?: boolean;
  /** Custom value formatter */
  format?: (value: number) => string;
  /** Callback when a bar is clicked */
  onItemClick?: (item: WaterfallItem) => void;
  /** Additional CSS class names */
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_COLORS = {
  increase: 'var(--wf-increase)',
  decrease: 'var(--wf-decrease)',
  total: 'var(--wf-total)',
} as const;

const PADDING = { top: 40, right: 20, bottom: 60, left: 20 };

function defaultFormat(v: number): string {
  return v.toLocaleString();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Financial waterfall (bridge) chart rendered as pure SVG.
 *
 * Used for P&L analysis, revenue breakdown, and variance reporting.
 * Bars grow upward for increases and downward for decreases. Total bars
 * span the full height from zero to the running total. Connector lines
 * link the end of one bar to the start of the next.
 *
 * @example
 * ```tsx
 * <WaterfallChart
 *   items={profitLossItems}
 *   showValues
 *   showConnectors
 *   format={(v) => `$${(v / 1000).toFixed(0)}K`}
 * />
 * ```
 */
export const WaterfallChart: React.FC<WaterfallChartProps> = ({
  items,
  height = 400,
  showValues = true,
  showConnectors = true,
  format = defaultFormat,
  onItemClick,
  className,
  access,
  accessReason,
}) => {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null;

  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const canInteract = !accessState.isDisabled && !accessState.isReadonly;

  // Compute running totals & bar positions
  const computed = useMemo(() => {
    if (items.length === 0) return { bars: [], minVal: 0, maxVal: 0 };

    let runningTotal = 0;
    const bars: Array<{
      item: WaterfallItem;
      start: number;
      end: number;
    }> = [];

    for (const item of items) {
      if (item.type === 'total') {
        bars.push({ item, start: 0, end: runningTotal });
      } else {
        const absVal = Math.abs(item.value);
        const sign = item.type === 'increase' ? 1 : -1;
        const delta = absVal * sign;
        const start = runningTotal;
        runningTotal += delta;
        bars.push({ item, start, end: runningTotal });
      }
    }

    const allValues = bars.flatMap((b) => [b.start, b.end]);
    allValues.push(0);
    const minVal = Math.min(...allValues);
    const maxVal = Math.max(...allValues);

    return { bars, minVal, maxVal };
  }, [items]);

  const handleClick = useCallback(
    (item: WaterfallItem) => {
      if (canInteract && onItemClick) {
        onItemClick(item);
      }
    },
    [canInteract, onItemClick],
  );

  if (items.length === 0) {
    return (
      <div
        className={cn(
          'p-8 text-center text-sm text-[var(--text-tertiary)]',
          className,
        )}
      >
        No data
      </div>
    );
  }

  const { bars, minVal, maxVal } = computed;
  const range = maxVal - minVal || 1;

  // SVG layout
  const barCount = bars.length;
  const barGap = 8;
  const barWidth = 48;
  const chartWidth = PADDING.left + barCount * (barWidth + barGap) - barGap + PADDING.right;
  const chartHeight = typeof height === 'number' ? height : 400;
  const plotHeight = chartHeight - PADDING.top - PADDING.bottom;

  const yScale = (value: number): number => {
    return PADDING.top + plotHeight - ((value - minVal) / range) * plotHeight;
  };

  const zeroY = yScale(0);

  return (
    <div
      className={cn(
        'border border-[var(--border-default)] rounded-lg bg-[var(--surface-default)] p-4',
        accessStyles(accessState.state),
        className,
      )}
      data-component="waterfall-chart"
      data-access-state={accessState.state}
      {...(accessState.isDisabled ? { 'aria-disabled': true } : {})}
      {...(accessReason ? { title: accessReason } : {})}
    >
      <svg
        width="100%"
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Waterfall chart"
      >
        {/* Zero line */}
        <line
          x1={PADDING.left}
          y1={zeroY}
          x2={chartWidth - PADDING.right}
          y2={zeroY}
          stroke="var(--border-default)"
          strokeWidth={1}
        />

        {bars.map((bar, i) => {
          const x = PADDING.left + i * (barWidth + barGap);
          const yTop = yScale(Math.max(bar.start, bar.end));
          const yBottom = yScale(Math.min(bar.start, bar.end));
          const barH = Math.max(yBottom - yTop, 2);
          const color =
            bar.item.color ?? DEFAULT_COLORS[bar.item.type];
          const isHovered = hoveredId === bar.item.id;
          const isClickable = canInteract && !!onItemClick;
          const displayValue =
            bar.item.type === 'total' ? bar.end : bar.item.value;

          return (
            <g key={bar.item.id}>
              {/* Connector line from previous bar */}
              {showConnectors && i > 0 && (
                <line
                  x1={PADDING.left + (i - 1) * (barWidth + barGap) + barWidth}
                  y1={yScale(bars[i - 1].end)}
                  x2={x}
                  y2={yScale(bars[i - 1].end)}
                  stroke="var(--border-default)"
                  strokeWidth={1}
                  strokeDasharray="4 3"
                />
              )}

              {/* Bar */}
              <rect
                x={x}
                y={yTop}
                width={barWidth}
                height={barH}
                fill={color}
                rx={3}
                opacity={isHovered ? 1 : 0.85}
                className={cn(
                  'transition-opacity duration-(--motion-duration-fast)',
                  isClickable && 'cursor-pointer',
                )}
                onClick={() => handleClick(bar.item)}
                onMouseEnter={() => setHoveredId(bar.item.id)}
                onMouseLeave={() => setHoveredId(null)}
              />

              {/* Hover outline */}
              {isHovered && (
                <rect
                  x={x - 1}
                  y={yTop - 1}
                  width={barWidth + 2}
                  height={barH + 2}
                  fill="none"
                  stroke={color}
                  strokeWidth={2}
                  rx={4}
                  pointerEvents="none"
                />
              )}

              {/* Value label */}
              {showValues && (
                <text
                  x={x + barWidth / 2}
                  y={
                    displayValue >= 0
                      ? yTop - 6
                      : yBottom + 14
                  }
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={600}
                  fill="var(--text-primary)"
                >
                  {format(displayValue)}
                </text>
              )}

              {/* X-axis label */}
              <text
                x={x + barWidth / 2}
                y={chartHeight - PADDING.bottom + 18}
                textAnchor="middle"
                fontSize={10}
                fill="var(--text-secondary)"
              >
                {bar.item.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

WaterfallChart.displayName = 'WaterfallChart';
export default WaterfallChart;
