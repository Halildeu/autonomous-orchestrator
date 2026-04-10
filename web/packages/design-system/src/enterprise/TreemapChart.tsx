import React from 'react';
import { cn } from '../utils/cn';
import {
  resolveAccessState,
  accessStyles,
  type AccessControlledProps,
} from '../internal/access-controller';
import { formatValue, type FormatOptions } from './types';

// ── Types ──

export interface TreemapItem {
  id: string;
  label: string;
  value: number;
  color?: string;
  children?: TreemapItem[];
}

interface LayoutRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface RenderedCell extends LayoutRect {
  item: TreemapItem;
  color: string;
}

/** Props for the TreemapChart component.
 * @example
 * ```tsx
 * <TreemapChart />
 * ```
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/treemap-chart)
 */
export interface TreemapChartProps extends AccessControlledProps {
  items: TreemapItem[];
  /** Chart width (default responsive via viewBox) */
  width?: number;
  /** Chart height (default 400) */
  height?: number;
  /** Number formatting */
  formatOptions?: FormatOptions;
  /** Click handler */
  onItemClick?: (item: TreemapItem) => void;
  /** Color palette for items without explicit color */
  palette?: string[];
  /** Minimum rect dimension to show label text */
  labelThreshold?: number;
  /** Additional class names */
  className?: string;
}

// ── Default palette ──

const DEFAULT_PALETTE = [
  'var(--action-primary)',
  'var(--state-info-text)',
  'var(--state-success-text)',
  'var(--state-warning-text)',
  'var(--state-error-text)',
  'var(--chart-purple)',
  'var(--chart-pink)',
  'var(--chart-cyan)',
  'var(--chart-amber)',
  'var(--chart-emerald)',
];

// ── Squarify algorithm ──

function flattenItems(items: TreemapItem[]): TreemapItem[] {
  const result: TreemapItem[] = [];
  for (const item of items) {
    if (item.children && item.children.length > 0) {
      result.push(...flattenItems(item.children));
    } else {
      result.push(item);
    }
  }
  return result;
}

function worstAspectRatio(row: number[], totalVal: number, sideLen: number): number {
  if (row.length === 0 || sideLen <= 0) return Infinity;
  const rowSum = row.reduce((a, b) => a + b, 0);
  const rowArea = (rowSum / totalVal) * (sideLen * sideLen);

  // Intentionally treating sideLen as the dimension we lay along
  // For squarified layout, we want aspect ratios close to 1
  let worst = 0;
  for (const val of row) {
    const fraction = val / rowSum;
    const cellArea = fraction * rowArea;
    const cellLen = rowArea / sideLen;
    const cellWidth = cellArea / cellLen;
    const ratio = Math.max(cellLen / cellWidth, cellWidth / cellLen);
    worst = Math.max(worst, ratio);
  }
  return worst;
}

function squarify(
  values: number[],
  indices: number[],
  rect: LayoutRect,
  totalValue: number,
  result: { index: number; rect: LayoutRect }[],
): void {
  if (indices.length === 0) return;
  if (indices.length === 1) {
    result.push({ index: indices[0], rect });
    return;
  }

  const { x, y, w, h } = rect;
  const isWide = w >= h;
  const sideLen = isWide ? h : w;

  if (sideLen <= 0 || totalValue <= 0) {
    // Degenerate — just stack
    for (const idx of indices) {
      result.push({ index: idx, rect: { x, y, w: Math.max(w, 0), h: Math.max(h, 0) } });
    }
    return;
  }

  const currentRow: number[] = [];
  const currentIndices: number[] = [];
  let remainingIndices = [...indices];
  let remainingValues = indices.map((i) => values[i]);

  // Build first row
  currentRow.push(remainingValues[0]);
  currentIndices.push(remainingIndices[0]);
  remainingValues = remainingValues.slice(1);
  remainingIndices = remainingIndices.slice(1);

  const sumAll = indices.reduce((s, i) => s + values[i], 0);

  while (remainingValues.length > 0) {
    const candidate = remainingValues[0];
    const withCandidate = [...currentRow, candidate];
    if (worstAspectRatio(withCandidate, sumAll, sideLen) <= worstAspectRatio(currentRow, sumAll, sideLen)) {
      currentRow.push(candidate);
      currentIndices.push(remainingIndices[0]);
      remainingValues = remainingValues.slice(1);
      remainingIndices = remainingIndices.slice(1);
    } else {
      break;
    }
  }

  // Lay out the row
  const rowSum = currentRow.reduce((a, b) => a + b, 0);
  const rowFraction = rowSum / sumAll;
  let offset = 0;

  for (let i = 0; i < currentRow.length; i++) {
    const cellFraction = currentRow[i] / rowSum;

    if (isWide) {
      const rowW = w * rowFraction;
      const cellH = h * cellFraction;
      result.push({
        index: currentIndices[i],
        rect: { x, y: y + offset, w: rowW, h: cellH },
      });
      offset += cellH;
    } else {
      const rowH = h * rowFraction;
      const cellW = w * cellFraction;
      result.push({
        index: currentIndices[i],
        rect: { x: x + offset, y, w: cellW, h: rowH },
      });
      offset += cellW;
    }
  }

  // Recurse on remaining
  if (remainingIndices.length > 0) {
    const remainingSum = remainingIndices.reduce((s, i) => s + values[i], 0);
    let nextRect: LayoutRect;
    if (isWide) {
      const usedW = w * rowFraction;
      nextRect = { x: x + usedW, y, w: w - usedW, h };
    } else {
      const usedH = h * rowFraction;
      nextRect = { x, y: y + usedH, w, h: h - usedH };
    }
    squarify(values, remainingIndices, nextRect, remainingSum, result);
  }
}

// ── Component ──

/** Space-filling treemap chart displaying hierarchical data as nested, proportionally-sized rectangles. */
export const TreemapChart: React.FC<TreemapChartProps> = ({
  items,
  width = 600,
  height = 400,
  formatOptions = {},
  onItemClick,
  palette = DEFAULT_PALETTE,
  labelThreshold = 30,
  className,
  access,
  accessReason,
}) => {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null;

  const [hoveredId, setHoveredId] = React.useState<string | null>(null);

  // Flatten nested items
  const flat = React.useMemo(() => flattenItems(items), [items]);

  // Compute layout
  const cells = React.useMemo<RenderedCell[]>(() => {
    if (flat.length === 0) return [];

    // Sort descending by value
    const sorted = flat
      .map((item, i) => ({ item, index: i }))
      .filter((e) => e.item.value > 0)
      .sort((a, b) => b.item.value - a.item.value);

    const values = sorted.map((e) => e.item.value);
    const indices = sorted.map((_, i) => i);
    const totalValue = values.reduce((a, b) => a + b, 0);

    const layoutResult: { index: number; rect: LayoutRect }[] = [];
    squarify(values, indices, { x: 0, y: 0, w: width, h: height }, totalValue, layoutResult);

    return layoutResult.map(({ index, rect }) => {
      const entry = sorted[index];
      return {
        ...rect,
        item: entry.item,
        color: entry.item.color ?? palette[entry.index % palette.length],
      };
    });
  }, [flat, width, height, palette]);

  if (flat.length === 0) {
    return (
      <div className={cn('p-8 text-center text-sm text-[var(--text-tertiary)]', className)}>
        No treemap data
      </div>
    );
  }

  return (
    <div
      className={cn(
        'border border-border-default rounded-lg bg-surface-default p-2 overflow-hidden',
        accessStyles(accessState.state),
        className,
      )}
      data-component="treemap-chart"
      data-access-state={accessState.state}
      title={accessReason}
    >
      <svg
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Treemap chart"
      >
        {cells.map((cell) => {
          const isHovered = hoveredId === cell.item.id;
          const showLabel = cell.w > labelThreshold && cell.h > labelThreshold;
          const showValue = cell.w > labelThreshold && cell.h > 50;

          return (
            <g
              key={cell.item.id}
              role={onItemClick ? 'button' : undefined}
              tabIndex={onItemClick ? 0 : undefined}
              className={cn(onItemClick && 'cursor-pointer')}
              onClick={() => onItemClick?.(cell.item)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onItemClick?.(cell.item); } }}
              onMouseEnter={() => setHoveredId(cell.item.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              {/* Background rect */}
              <rect
                x={cell.x + 1}
                y={cell.y + 1}
                width={Math.max(0, cell.w - 2)}
                height={Math.max(0, cell.h - 2)}
                fill={cell.color}
                opacity={isHovered ? 1 : 0.8}
                rx={3}
                style={{ transition: 'opacity 0.15s ease' }}
              />
              {/* Hover border */}
              {isHovered && (
                <rect
                  x={cell.x + 1}
                  y={cell.y + 1}
                  width={Math.max(0, cell.w - 2)}
                  height={Math.max(0, cell.h - 2)}
                  fill="none"
                  stroke="var(--text-primary)"
                  strokeWidth={2}
                  rx={3}
                />
              )}
              {/* Label */}
              {showLabel && (
                <text
                  x={cell.x + cell.w / 2}
                  y={cell.y + cell.h / 2 - (showValue ? 6 : 0)}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={Math.min(13, cell.w / 8)}
                  fontWeight={600}
                  fill="var(--text-inverse)"
                  style={{ pointerEvents: 'none' }}
                >
                  {cell.item.label}
                </text>
              )}
              {/* Value */}
              {showValue && (
                <text
                  x={cell.x + cell.w / 2}
                  y={cell.y + cell.h / 2 + 12}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={Math.min(11, cell.w / 10)}
                  fill="var(--text-inverse)"
                  opacity={0.85}
                  style={{ pointerEvents: 'none' }}
                >
                  {formatValue(cell.item.value, formatOptions)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

TreemapChart.displayName = 'TreemapChart';
export default TreemapChart;
