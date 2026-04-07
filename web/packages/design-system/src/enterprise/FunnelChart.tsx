import React from 'react';
import { cn } from '../utils/cn';
import {
  resolveAccessState,
  accessStyles,
  type AccessControlledProps,
} from '../internal/access-controller';
import { formatValue, type FormatOptions } from './types';

// ── Types ──

export interface FunnelStage {
  id: string;
  label: string;
  value: number;
  color?: string;
}

/** Funnel visualization with conversion rates between stages.
 * @example
 * ```tsx
 * <FunnelChart />
 * ```
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/funnel-chart)
 */
export interface FunnelChartProps extends AccessControlledProps {
  /** Ordered funnel stages from widest to narrowest */
  stages: FunnelStage[];
  /** Render direction: vertical uses trapezoid shapes, horizontal uses bars */
  orientation?: 'vertical' | 'horizontal';
  /** Enable entrance animation when the chart mounts */
  animated?: boolean;
  /** Number formatting options for stage values */
  formatOptions?: FormatOptions;
  /** Called when a funnel stage is clicked */
  onStageClick?: (stage: FunnelStage) => void;
  /** Additional CSS class names for the root element */
  className?: string;
}

// ── Helpers ──

function computeConversionRate(current: number, previous: number): number {
  if (previous === 0) return 0;
  return Math.round((current / previous) * 1000) / 10;
}

const DEFAULT_COLORS = [
  'var(--action-primary)',
  'var(--state-info-text)',
  'var(--state-success-text)',
  'var(--state-warning-text)',
  'var(--state-error-text)',
  'var(--chart-purple)',
  'var(--chart-pink)',
  'var(--chart-cyan)',
];

// ── Component ──

/** Funnel visualization with conversion rates between stages. */
export const FunnelChart: React.FC<FunnelChartProps> = ({
  stages,
  orientation = 'vertical',
  animated = true,
  formatOptions = {},
  onStageClick,
  className,
  access,
  accessReason,
}) => {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null;

  const [hoveredId, setHoveredId] = React.useState<string | null>(null);
  const [visible, setVisible] = React.useState(!animated);

  React.useEffect(() => {
    if (animated) {
      const timer = setTimeout(() => setVisible(true), 50);
      return () => clearTimeout(timer);
    }
  }, [animated]);

  if (stages.length === 0) {
    return (
      <div className={cn('p-8 text-center text-sm text-[var(--text-tertiary)]', className)}>
        No funnel data
      </div>
    );
  }

  const maxValue = Math.max(...stages.map(s => s.value), 1);
  const isVertical = orientation === 'vertical';

  // SVG dimensions
  const STAGE_HEIGHT = 48;
  const GAP = 4;
  const LABEL_AREA = 180;
  const CHART_WIDTH = 320;
  const TOTAL_WIDTH = LABEL_AREA + CHART_WIDTH + LABEL_AREA;
  const TOTAL_HEIGHT = stages.length * (STAGE_HEIGHT + GAP) - GAP;

  // For horizontal: swap axes
  const HORIZ_STAGE_WIDTH = 80;
  const HORIZ_CHART_HEIGHT = 240;
  const HORIZ_TOTAL_WIDTH = stages.length * (HORIZ_STAGE_WIDTH + GAP) - GAP;

  if (!isVertical) {
    // Horizontal funnel
    return (
      <div
        className={cn('border border-border-default rounded-lg bg-surface-default p-4', accessStyles(accessState.state), className)}
        data-component="funnel-chart"
        data-access-state={accessState.state}
        title={accessReason}
      >
        <svg width="100%" viewBox={`0 0 ${HORIZ_TOTAL_WIDTH} ${HORIZ_CHART_HEIGHT + 80}`} preserveAspectRatio="xMidYMid meet">
          {stages.map((stage, i) => {
            const widthRatio = stage.value / maxValue;
            const barHeight = HORIZ_CHART_HEIGHT * widthRatio;
            const color = stage.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length];
            const x = i * (HORIZ_STAGE_WIDTH + GAP);
            const y = HORIZ_CHART_HEIGHT - barHeight;
            const isHovered = hoveredId === stage.id;
            const convRate = i > 0 ? computeConversionRate(stage.value, stages[i - 1].value) : 100;

            return (
              <g
                key={stage.id}
                role={onStageClick ? 'button' : undefined}
                tabIndex={onStageClick ? 0 : undefined}
                className={cn(onStageClick && 'cursor-pointer')}
                onClick={() => onStageClick?.(stage)}
                onKeyDown={(e) => {
                  if ((e.key === 'Enter' || e.key === ' ') && onStageClick) {
                    e.preventDefault();
                    onStageClick(stage);
                  }
                }}
                onMouseEnter={() => setHoveredId(stage.id)}
                onMouseLeave={() => setHoveredId(null)}
                aria-label={stage.label}
              >
                <rect
                  x={x}
                  y={visible ? y : HORIZ_CHART_HEIGHT}
                  width={HORIZ_STAGE_WIDTH}
                  height={visible ? barHeight : 0}
                  fill={color}
                  opacity={isHovered ? 1 : 0.8}
                  rx={4}
                  style={{ transition: animated ? 'all 0.6s ease-out' : undefined, transitionDelay: animated ? `${i * 100}ms` : undefined }}
                />
                {/* Label */}
                <text
                  x={x + HORIZ_STAGE_WIDTH / 2}
                  y={HORIZ_CHART_HEIGHT + 16}
                  textAnchor="middle"
                  fontSize={11}
                  fill="var(--text-secondary)"
                >
                  {stage.label}
                </text>
                {/* Value */}
                <text
                  x={x + HORIZ_STAGE_WIDTH / 2}
                  y={HORIZ_CHART_HEIGHT + 32}
                  textAnchor="middle"
                  fontSize={12}
                  fontWeight={600}
                  fill="var(--text-primary)"
                >
                  {formatValue(stage.value, formatOptions)}
                </text>
                {/* Conversion rate */}
                {i > 0 && (
                  <text
                    x={x + HORIZ_STAGE_WIDTH / 2}
                    y={HORIZ_CHART_HEIGHT + 48}
                    textAnchor="middle"
                    fontSize={10}
                    fill="var(--text-tertiary)"
                  >
                    {convRate}%
                  </text>
                )}
                {/* Tooltip on hover */}
                {isHovered && (
                  <rect x={x} y={y - 2} width={HORIZ_STAGE_WIDTH} height={barHeight + 4} fill="transparent" stroke={color} strokeWidth={2} rx={4} />
                )}
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  // Vertical funnel (default) - trapezoid shapes
  return (
    <div
      className={cn('border border-border-default rounded-lg bg-surface-default p-4', accessStyles(accessState.state), className)}
      data-component="funnel-chart"
      data-access-state={accessState.state}
      title={accessReason}
    >
      <svg width="100%" viewBox={`0 0 ${TOTAL_WIDTH} ${TOTAL_HEIGHT}`} preserveAspectRatio="xMidYMid meet">
        {stages.map((stage, i) => {
          const widthRatio = stage.value / maxValue;
          const nextWidthRatio = i < stages.length - 1 ? stages[i + 1].value / maxValue : widthRatio * 0.6;
          const color = stage.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length];
          const isHovered = hoveredId === stage.id;
          const convRate = i > 0 ? computeConversionRate(stage.value, stages[i - 1].value) : 100;

          const y = i * (STAGE_HEIGHT + GAP);
          const cx = LABEL_AREA + CHART_WIDTH / 2;

          const topHalfWidth = (CHART_WIDTH / 2) * widthRatio;
          const bottomHalfWidth = (CHART_WIDTH / 2) * nextWidthRatio;

          // Trapezoid path
          const topLeft = cx - (visible ? topHalfWidth : 0);
          const topRight = cx + (visible ? topHalfWidth : 0);
          const bottomLeft = cx - (visible ? bottomHalfWidth : 0);
          const bottomRight = cx + (visible ? bottomHalfWidth : 0);

          const path = `M ${topLeft} ${y} L ${topRight} ${y} L ${bottomRight} ${y + STAGE_HEIGHT} L ${bottomLeft} ${y + STAGE_HEIGHT} Z`;

          return (
            <g
              key={stage.id}
              role={onStageClick ? 'button' : undefined}
              tabIndex={onStageClick ? 0 : undefined}
              className={cn(onStageClick && 'cursor-pointer')}
              onClick={() => onStageClick?.(stage)}
              onKeyDown={(e) => {
                if ((e.key === 'Enter' || e.key === ' ') && onStageClick) {
                  e.preventDefault();
                  onStageClick(stage);
                }
              }}
              onMouseEnter={() => setHoveredId(stage.id)}
              onMouseLeave={() => setHoveredId(null)}
              aria-label={stage.label}
            >
              <path
                d={path}
                fill={color}
                opacity={isHovered ? 1 : 0.75}
                style={{ transition: animated ? 'all 0.6s ease-out' : undefined, transitionDelay: animated ? `${i * 120}ms` : undefined }}
              />
              {/* Hover outline */}
              {isHovered && (
                <path d={path} fill="none" stroke={color} strokeWidth={2} />
              )}
              {/* Left label */}
              <text
                x={LABEL_AREA - 8}
                y={y + STAGE_HEIGHT / 2 + 4}
                textAnchor="end"
                fontSize={12}
                fontWeight={500}
                fill="var(--text-primary)"
              >
                {stage.label}
              </text>
              {/* Right: value + conversion */}
              <text
                x={LABEL_AREA + CHART_WIDTH + 8}
                y={y + STAGE_HEIGHT / 2}
                textAnchor="start"
                fontSize={13}
                fontWeight={700}
                fill="var(--text-primary)"
              >
                {formatValue(stage.value, formatOptions)}
              </text>
              {i > 0 && (
                <text
                  x={LABEL_AREA + CHART_WIDTH + 8}
                  y={y + STAGE_HEIGHT / 2 + 16}
                  textAnchor="start"
                  fontSize={10}
                  fill="var(--text-tertiary)"
                >
                  {convRate}% conversion
                </text>
              )}
              {/* Center label when wide enough */}
              {visible && widthRatio > 0.3 && (
                <text
                  x={cx}
                  y={y + STAGE_HEIGHT / 2 + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={600}
                  fill="var(--text-inverse)"
                >
                  {formatValue(stage.value, formatOptions)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

FunnelChart.displayName = 'FunnelChart';
export default FunnelChart;
