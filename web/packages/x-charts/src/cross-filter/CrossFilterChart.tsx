/**
 * CrossFilterChart — Wrapper that auto-wires any chart to the cross-filter bus
 *
 * Instead of modifying each chart's internals, this wrapper:
 * 1. Intercepts onDataPointClick → emits cross-filter
 * 2. Receives incoming filters → renders filter indicator
 * 3. Provides clear button for own filters
 *
 * Usage:
 * ```tsx
 * <CrossFilterProvider>
 *   <CrossFilterChart chartId="revenue" emitFields={["category"]}>
 *     <BarChart data={data} />
 *   </CrossFilterChart>
 * </CrossFilterProvider>
 * ```
 */
import React, { cloneElement, isValidElement, useCallback } from 'react';
import { useChartCrossFilter } from './useChartCrossFilter';
import type { UseChartCrossFilterOptions } from './useChartCrossFilter';

export interface CrossFilterChartProps extends UseChartCrossFilterOptions {
  children: React.ReactElement;
  /** Show filter indicator badge. @default true */
  showIndicator?: boolean;
  /** Additional class name for wrapper. */
  className?: string;
}

export function CrossFilterChart({
  chartId,
  emitFields = [],
  enabled = true,
  showIndicator = true,
  className,
  children,
}: CrossFilterChartProps) {
  const { activeFilters, onChartClick, isFiltered, filterCount, clearOwnFilter } =
    useChartCrossFilter({ chartId, emitFields, enabled });

  const handleClick = useCallback(
    (event: { datum: Record<string, unknown> }) => {
      onChartClick(event.datum);
    },
    [onChartClick],
  );

  // Clone child chart and inject onDataPointClick
  const chart = isValidElement(children)
    ? cloneElement(children as React.ReactElement<{ onDataPointClick?: (e: unknown) => void }>, {
        onDataPointClick: enabled ? handleClick : (children.props as Record<string, unknown>).onDataPointClick,
      })
    : children;

  return (
    <div className={className} style={{ position: 'relative' }}>
      {chart}
      {showIndicator && isFiltered && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '2px 8px',
            borderRadius: 12,
            fontSize: 11,
            fontWeight: 500,
            background: 'var(--surface-raised, #f3f4f6)',
            color: 'var(--text-secondary, #6b7280)',
            border: '1px solid var(--border-subtle, #e5e7eb)',
          }}
          data-testid="cross-filter-indicator"
        >
          <span>{filterCount} filtre aktif</span>
          <button
            onClick={clearOwnFilter}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              fontSize: 13,
              lineHeight: 1,
              color: 'var(--text-secondary, #6b7280)',
            }}
            aria-label="Filtreleri temizle"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}

CrossFilterChart.displayName = 'CrossFilterChart';

export default CrossFilterChart;
