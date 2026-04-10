import React, { useMemo, useCallback } from 'react';
import { cn } from '../utils/cn';
import {
  resolveAccessState,
  accessStyles,
  type AccessControlledProps,
} from '../internal/access-controller';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SWOTItem {
  id: string;
  text: string;
  priority?: 'high' | 'medium' | 'low';
}

export type SWOTQuadrant = 'S' | 'W' | 'O' | 'T';

/** Props for the SWOTMatrix component.
 * @example
 * ```tsx
 * <SWOTMatrix strengths={[]} weaknesses={[]} opportunities={[]} threats={[]} />
 * ```
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/swot-matrix)
 */
export interface SWOTMatrixProps extends AccessControlledProps {
  /** Strength items (top-left quadrant) */
  strengths: SWOTItem[];
  /** Weakness items (top-right quadrant) */
  weaknesses: SWOTItem[];
  /** Opportunity items (bottom-left quadrant) */
  opportunities: SWOTItem[];
  /** Threat items (bottom-right quadrant) */
  threats: SWOTItem[];
  /** Optional title displayed above the matrix */
  title?: string;
  /** Called when an item chip is clicked */
  onItemClick?: (quadrant: SWOTQuadrant, item: SWOTItem) => void;
  /** Compact mode reduces spacing and font sizes */
  compact?: boolean;
  /** Additional CSS class names for the root element */
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PRIORITY_DOT_COLORS: Record<string, string> = {
  high: 'var(--state-error-text)',
  medium: 'var(--state-warning-text)',
  low: 'var(--state-success-text)',
};

interface QuadrantConfig {
  key: SWOTQuadrant;
  label: string;
  subtitle: string;
  bg: string;
  border: string;
  headerBg: string;
  headerText: string;
  itemProp: 'strengths' | 'weaknesses' | 'opportunities' | 'threats';
}

const QUADRANT_CONFIG: QuadrantConfig[] = [
  {
    key: 'S',
    label: 'Strengths',
    subtitle: 'Internal positive',
    bg: 'var(--state-success-bg)',
    border: 'var(--state-success-text)',
    headerBg: 'var(--state-success-text)',
    headerText: 'var(--text-inverse)',
    itemProp: 'strengths',
  },
  {
    key: 'W',
    label: 'Weaknesses',
    subtitle: 'Internal negative',
    bg: 'var(--state-error-bg)',
    border: 'var(--state-error-text)',
    headerBg: 'var(--state-error-text)',
    headerText: 'var(--text-inverse)',
    itemProp: 'weaknesses',
  },
  {
    key: 'O',
    label: 'Opportunities',
    subtitle: 'External positive',
    bg: 'var(--state-info-bg)',
    border: 'var(--state-info-text)',
    headerBg: 'var(--state-info-text)',
    headerText: 'var(--text-inverse)',
    itemProp: 'opportunities',
  },
  {
    key: 'T',
    label: 'Threats',
    subtitle: 'External negative',
    bg: 'var(--state-warning-bg)',
    border: 'var(--state-warning-text)',
    headerBg: 'var(--state-warning-text)',
    headerText: 'var(--text-inverse)',
    itemProp: 'threats',
  },
];

// ---------------------------------------------------------------------------
// Item chip sub-component
// ---------------------------------------------------------------------------

interface SWOTChipProps {
  item: SWOTItem;
  quadrant: SWOTQuadrant;
  canInteract: boolean;
  compact: boolean;
  onItemClick?: (quadrant: SWOTQuadrant, item: SWOTItem) => void;
}

const SWOTChip: React.FC<SWOTChipProps> = ({ item, quadrant, canInteract, compact, onItemClick }) => {
  const handleClick = useCallback(() => {
    if (canInteract && onItemClick) {
      onItemClick(quadrant, item);
    }
  }, [canInteract, onItemClick, quadrant, item]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.key === 'Enter' || e.key === ' ') && canInteract && onItemClick) {
        e.preventDefault();
        onItemClick(quadrant, item);
      }
    },
    [canInteract, onItemClick, quadrant, item],
  );

  const isClickable = canInteract && !!onItemClick;

  return (
    <span
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onClick={handleClick}
      onKeyDown={isClickable ? handleKeyDown : undefined}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md',
        'bg-[var(--surface-default)] border border-[var(--border-subtle)]',
        'text-[var(--text-primary)]',
        'transition-colors duration-(--motion-duration-fast)',
        compact ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs',
        isClickable && 'cursor-pointer hover:bg-[var(--surface-muted)] focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--focus-ring)]',
      )}
      data-priority={item.priority}
      data-quadrant={quadrant}
    >
      {item.priority && (
        <span
          className={cn('inline-block rounded-full shrink-0', compact ? 'w-1.5 h-1.5' : 'w-2 h-2')}
          style={{ backgroundColor: PRIORITY_DOT_COLORS[item.priority] }}
          aria-label={`${item.priority} priority`}
        />
      )}
      <span className={cn('truncate', compact ? 'max-w-[120px]' : 'max-w-[180px]')}>{item.text}</span>
    </span>
  );
};

// ---------------------------------------------------------------------------
// Quadrant sub-component
// ---------------------------------------------------------------------------

interface QuadrantPanelProps {
  config: QuadrantConfig;
  items: SWOTItem[];
  canInteract: boolean;
  compact: boolean;
  onItemClick?: (quadrant: SWOTQuadrant, item: SWOTItem) => void;
  position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
}

const QuadrantPanel: React.FC<QuadrantPanelProps> = ({ config, items, canInteract, compact, onItemClick, position }) => {
  const borderRadius = useMemo(() => {
    switch (position) {
      case 'top-left': return '0.5rem 0 0 0';
      case 'top-right': return '0 0.5rem 0 0';
      case 'bottom-left': return '0 0 0 0.5rem';
      case 'bottom-right': return '0 0 0.5rem 0';
    }
  }, [position]);

  return (
    <div
      className={cn('flex flex-col', compact ? 'min-h-[100px]' : 'min-h-[160px]')}
      style={{
        backgroundColor: config.bg,
        borderRadius,
        border: `1px solid ${config.border}`,
      }}
      role="region"
      aria-label={`${config.label} quadrant`}
    >
      {/* Header */}
      <div
        className={cn('flex items-center justify-between', compact ? 'px-2 py-1' : 'px-3 py-2')}
        style={{
          backgroundColor: config.headerBg,
          color: config.headerText,
          borderRadius: position.startsWith('top')
            ? position === 'top-left' ? '0.5rem 0 0 0' : '0 0.5rem 0 0'
            : undefined,
        }}
      >
        <div>
          <span className={cn('font-semibold', compact ? 'text-xs' : 'text-sm')}>{config.label}</span>
          {!compact && <span className="text-[10px] ml-2 opacity-80">{config.subtitle}</span>}
        </div>
        <span className={cn('font-mono opacity-80', compact ? 'text-[10px]' : 'text-xs')}>{items.length}</span>
      </div>

      {/* Items */}
      <div className={cn('flex flex-wrap gap-1.5 flex-1', compact ? 'p-2' : 'p-3')}>
        {items.length === 0 && (
          <span className="text-xs text-[var(--text-tertiary)] italic">
            No items
          </span>
        )}
        {items.map((item) => (
          <SWOTChip
            key={item.id}
            item={item}
            quadrant={config.key}
            canInteract={canInteract}
            compact={compact}
            onItemClick={onItemClick}
          />
        ))}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const POSITIONS: Array<'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'> = [
  'top-left', 'top-right', 'bottom-left', 'bottom-right',
];

/** Strategic SWOT analysis displayed as a 2x2 quadrant grid with color-coded sections. */
export function SWOTMatrix({
  strengths,
  weaknesses,
  opportunities,
  threats,
  title,
  onItemClick,
  compact = false,
  className,
  access,
  accessReason,
}: SWOTMatrixProps) {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null;

  const canInteract = !accessState.isDisabled && !accessState.isReadonly;

  const itemsByQuadrant: Record<string, SWOTItem[]> = useMemo(
    () => ({
      strengths,
      weaknesses,
      opportunities,
      threats,
    }),
    [strengths, weaknesses, opportunities, threats],
  );

  const totalItems = strengths.length + weaknesses.length + opportunities.length + threats.length;

  return (
    <div
      className={cn(
        'inline-block w-full max-w-3xl',
        accessStyles(accessState.state),
        className,
      )}
      data-component="swot-matrix"
      data-access-state={accessState.state}
      role="group"
      aria-label={title ?? 'SWOT Analysis'}
      {...(accessState.isDisabled ? { 'aria-disabled': true } : {})}
      {...(accessReason ? { title: accessReason } : {})}
    >
      {/* Title */}
      {title && (
        <h3 className={cn('font-semibold text-[var(--text-primary)]', compact ? 'text-sm mb-2' : 'text-base mb-3')}>
          {title}
        </h3>
      )}

      {/* Summary strip */}
      {!compact && (
        <div className="flex items-center gap-4 mb-3 text-xs text-[var(--text-secondary)]">
          <span>Total: {totalItems} items</span>
          {QUADRANT_CONFIG.map((q) => (
            <span key={q.key} className="inline-flex items-center gap-1">
              <span
                className="inline-block w-2.5 h-2.5 rounded-xs"
                style={{ backgroundColor: q.headerBg }}
                aria-hidden="true"
              />
              {q.label}: {itemsByQuadrant[q.itemProp].length}
            </span>
          ))}
        </div>
      )}

      {/* 2x2 Grid */}
      <div className={cn('grid grid-cols-2 bg-[var(--border-default)] rounded-lg overflow-hidden', compact ? 'gap-px' : 'gap-0.5')}>
        {QUADRANT_CONFIG.map((config, idx) => (
          <QuadrantPanel
            key={config.key}
            config={config}
            items={itemsByQuadrant[config.itemProp]}
            canInteract={canInteract}
            compact={compact}
            onItemClick={onItemClick}
            position={POSITIONS[idx]}
          />
        ))}
      </div>

      {/* Priority legend */}
      <div className={cn('flex items-center gap-4', compact ? 'mt-2' : 'mt-3')} role="list" aria-label="Priority legend">
        {(['high', 'medium', 'low'] as const).map((priority) => (
          <div key={priority} className="flex items-center gap-1.5" role="listitem">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: PRIORITY_DOT_COLORS[priority] }}
              aria-hidden="true"
            />
            <span className="text-[10px] text-[var(--text-secondary)] capitalize">{priority}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

SWOTMatrix.displayName = 'SWOTMatrix';
export default SWOTMatrix;
