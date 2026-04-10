import React from 'react';
import { cn } from '../utils/cn';
import {
  resolveAccessState,
  accessStyles,
  type AccessControlledProps,
} from '../internal/access-controller';

// ── Types ──

export type TrainingStatus = 'not-started' | 'in-progress' | 'completed' | 'expired' | 'overdue';

export interface TrainingItem {
  id: string;
  title: string;
  category: string;
  status: TrainingStatus;
  progress: number; // 0-100
  dueDate?: Date;
  assignee?: string;
  mandatory?: boolean;
}

/** Training compliance tracker with progress bars, status filters, and collapsible groups.
 * @example
 * ```tsx
 * <TrainingTracker />
 * ```
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/training-tracker)
 */
export interface TrainingTrackerProps extends AccessControlledProps {
  /** Training items to display */
  items: TrainingItem[];
  /** Grouping strategy for organizing the items */
  groupBy?: 'category' | 'status' | 'assignee';
  /** Initially active status filters; defaults to all statuses */
  filterStatuses?: TrainingStatus[];
  /** Called when a training item row is clicked */
  onItemClick?: (item: TrainingItem) => void;
  /** Additional CSS class names for the root element */
  className?: string;
}

// ── Status config ──

const STATUS_CONFIG: Record<TrainingStatus, { label: string; bg: string; text: string }> = {
  'not-started': { label: 'Not Started', bg: 'bg-surface-muted', text: 'text-[var(--text-tertiary)]' },
  'in-progress': { label: 'In Progress', bg: 'bg-state-info-bg', text: 'text-state-info-text' },
  'completed': { label: 'Completed', bg: 'bg-state-success-bg', text: 'text-state-success-text' },
  'expired': { label: 'Expired', bg: 'bg-state-warning-bg', text: 'text-state-warning-text' },
  'overdue': { label: 'Overdue', bg: 'bg-state-danger-bg', text: 'text-state-danger-text' },
};

const STATUS_BAR_COLOR: Record<TrainingStatus, string> = {
  'not-started': 'var(--text-tertiary)',
  'in-progress': 'var(--state-info-text)',
  'completed': 'var(--state-success-text)',
  'expired': 'var(--state-warning-text)',
  'overdue': 'var(--state-error-text)',
};

const ALL_STATUSES: TrainingStatus[] = ['not-started', 'in-progress', 'completed', 'expired', 'overdue'];

// ── Helpers ──

function isOverdue(item: TrainingItem): boolean {
  if (!item.dueDate) return false;
  return item.dueDate < new Date() && item.status !== 'completed';
}

function formatDate(date: Date): string {
  return date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' });
}

function groupItems(items: TrainingItem[], groupBy: 'category' | 'status' | 'assignee'): Map<string, TrainingItem[]> {
  const map = new Map<string, TrainingItem[]>();
  for (const item of items) {
    let key: string;
    switch (groupBy) {
      case 'category': key = item.category; break;
      case 'status': key = STATUS_CONFIG[item.status].label; break;
      case 'assignee': key = item.assignee ?? 'Unassigned'; break;
    }
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return map;
}

// ── Component ──

/** Training compliance tracker with progress bars, status filters, and collapsible groups. */
export const TrainingTracker: React.FC<TrainingTrackerProps> = ({
  items,
  groupBy = 'category',
  filterStatuses,
  onItemClick,
  className,
  access,
  accessReason,
}) => {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null;

  const [activeFilters, setActiveFilters] = React.useState<Set<TrainingStatus>>(
    () => new Set(filterStatuses ?? ALL_STATUSES),
  );
  const [collapsedGroups, setCollapsedGroups] = React.useState<Set<string>>(new Set());

  const toggleFilter = (status: TrainingStatus) => {
    setActiveFilters(prev => {
      const next = new Set(prev);
      if (next.has(status)) {
        if (next.size > 1) next.delete(status); // keep at least one
      } else {
        next.add(status);
      }
      return next;
    });
  };

  const toggleGroup = (key: string) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Filter items
  const filteredItems = items.filter(item => activeFilters.has(item.status));
  const grouped = groupItems(filteredItems, groupBy);

  return (
    <div
      className={cn(
        'border border-border-default rounded-lg bg-surface-default overflow-hidden',
        accessStyles(accessState.state),
        className,
      )}
      data-component="training-tracker"
      data-access-state={accessState.state}
      title={accessReason}
    >
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border-default bg-surface-muted px-4 py-3">
        <span className="text-xs font-medium text-text-secondary mr-1">Filter:</span>
        {ALL_STATUSES.map(status => {
          const config = STATUS_CONFIG[status];
          const isActive = activeFilters.has(status);
          const count = items.filter(i => i.status === status).length;
          return (
            <button
              key={status}
              className={cn(
                'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-all',
                isActive ? `${config.bg} ${config.text} ring-1 ring-current/20` : 'bg-transparent text-[var(--text-tertiary)] hover:bg-surface-default',
              )}
              onClick={() => toggleFilter(status)}
            >
              {config.label}
              <span className="text-[10px] opacity-70">({count})</span>
            </button>
          );
        })}
      </div>

      {/* Grouped items */}
      <div className="divide-y divide-border-subtle">
        {Array.from(grouped.entries()).map(([groupKey, groupItems]) => {
          const isCollapsed = collapsedGroups.has(groupKey);
          return (
            <div key={groupKey}>
              {/* Group header */}
              <button
                className="flex w-full items-center gap-2 bg-surface-muted/50 px-4 py-2 text-left hover:bg-surface-muted"
                onClick={() => toggleGroup(groupKey)}
              >
                <span className="text-[10px] text-[var(--text-tertiary)]">
                  {isCollapsed ? '\u25B6' : '\u25BC'}
                </span>
                <span className="text-sm font-semibold text-text-primary">{groupKey}</span>
                <span className="text-xs text-[var(--text-tertiary)]">({groupItems.length})</span>
              </button>

              {/* Items */}
              {!isCollapsed && (
                <div className="divide-y divide-border-subtle">
                  {groupItems.map(item => {
                    const overdue = isOverdue(item);
                    const statusCfg = STATUS_CONFIG[overdue && item.status !== 'completed' ? 'overdue' : item.status];
                    const barColor = STATUS_BAR_COLOR[overdue && item.status !== 'completed' ? 'overdue' : item.status];

                    return (
                      <div
                        key={item.id}
                        className={cn(
                          'flex items-center gap-3 px-4 py-3 transition-colors',
                          onItemClick && 'cursor-pointer hover:bg-surface-muted/40',
                          overdue && item.status !== 'completed' && 'border-l-2 border-l-[var(--state-error-text)]',
                        )}
                        onClick={() => onItemClick?.(item)}
                      >
                        {/* Mandatory star */}
                        <div className="w-4 shrink-0 text-center">
                          {item.mandatory && (
                            <span className="text-state-warning-text text-sm" title="Mandatory">{'\u2605'}</span>
                          )}
                        </div>

                        {/* Title + category */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-text-primary truncate">
                              {item.title}
                            </span>
                            <span className="inline-flex items-center rounded-full bg-surface-muted px-2 py-0.5 text-[10px] font-medium text-text-secondary shrink-0">
                              {item.category}
                            </span>
                          </div>

                          {/* Progress bar */}
                          <div className="mt-1.5 flex items-center gap-2">
                            <div className="h-1.5 flex-1 rounded-full bg-surface-muted overflow-hidden max-w-[200px]">
                              <div
                                className="h-full rounded-full transition-all duration-(--motion-duration-slow)"
                                style={{ width: `${item.progress}%`, backgroundColor: barColor }}
                              />
                            </div>
                            <span className="text-[10px] font-mono text-[var(--text-tertiary)] w-8 text-right">
                              {item.progress}%
                            </span>
                          </div>
                        </div>

                        {/* Status badge */}
                        <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold shrink-0', statusCfg.bg, statusCfg.text)}>
                          {statusCfg.label}
                        </span>

                        {/* Due date */}
                        {item.dueDate && (
                          <span className={cn('text-xs shrink-0', overdue && item.status !== 'completed' ? 'text-state-danger-text font-medium' : 'text-[var(--text-tertiary)]')}>
                            {formatDate(item.dueDate)}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {filteredItems.length === 0 && (
        <div className="p-8 text-center text-sm text-[var(--text-tertiary)]">
          No training items match the current filters
        </div>
      )}
    </div>
  );
};

TrainingTracker.displayName = 'TrainingTracker';
export default TrainingTracker;
