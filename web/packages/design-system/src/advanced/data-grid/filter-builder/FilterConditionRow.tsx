/**
 * FilterConditionRow — Single filter condition row.
 *
 * Layout: [⠿ DnD] [↑] [↓]  [Column ▼] [Operator ▼] [Value]  [Clone] [Lock] [Delete]
 */
import React, { useMemo } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Trash2, ChevronUp, ChevronDown, Copy, Lock, Unlock, GripVertical } from 'lucide-react';
import type { ColDef } from 'ag-grid-community';
import type { FilterCondition, FilterType } from './types';
import { TEXT_OPERATORS, NUMBER_OPERATORS, DATE_OPERATORS } from './filterModelConverter';
import { FilterValueEditor } from './FilterValueEditor';

interface FilterConditionRowProps {
  condition: FilterCondition;
  columnDefs: ColDef[];
  onUpdate: (id: string, updates: Partial<FilterCondition>) => void;
  onRemove: (id: string) => void;
  onMove: (id: string, direction: 'up' | 'down') => void;
  onClone: (id: string) => void;
  onToggleLock: (id: string) => void;
  canRemove: boolean;
  parentLocked?: boolean;
}

const SELECT_CLASS =
  'h-8 rounded-md border border-border-subtle bg-surface-default px-2 text-xs text-text-primary focus:border-action-primary focus:outline-none focus:ring-1 focus:ring-action-primary disabled:cursor-not-allowed disabled:opacity-60';

function detectFilterType(colDef?: ColDef): FilterType {
  if (!colDef) return 'text';
  const f = colDef.filter;
  if (f === 'agSetColumnFilter') return 'set';
  if (f === 'agNumberColumnFilter') return 'number';
  if (f === 'agDateColumnFilter') return 'date';
  if (f === 'agMultiColumnFilter' && colDef.filterParams) {
    const filters = (colDef.filterParams as Record<string, unknown>).filters as Array<{ filter: string }> | undefined;
    if (filters?.[0]?.filter === 'agNumberColumnFilter') return 'number';
    if (filters?.[0]?.filter === 'agDateColumnFilter') return 'date';
    if (filters?.[0]?.filter === 'agSetColumnFilter') return 'set';
  }
  return 'text';
}

function getOperators(filterType: FilterType) {
  switch (filterType) {
    case 'number': return NUMBER_OPERATORS;
    case 'date': return DATE_OPERATORS;
    case 'set': return [{ value: 'in', label: 'İçinde' }];
    default: return TEXT_OPERATORS;
  }
}

function getSetValues(colDef?: ColDef): string[] {
  if (!colDef?.filterParams) return [];
  const p = colDef.filterParams as Record<string, unknown>;
  if (Array.isArray(p.values)) return p.values as string[];
  return [];
}

export const FilterConditionRow: React.FC<FilterConditionRowProps> = ({
  condition,
  columnDefs,
  onUpdate,
  onRemove,
  onMove,
  onClone,
  onToggleLock,
  canRemove,
  parentLocked = false,
}) => {
  const isLocked = condition.locked || parentLocked;

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: condition.id,
    disabled: isLocked,
  });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 10 : undefined,
  };

  const filterableColumns = useMemo(
    () =>
      columnDefs
        .filter((c) => c.field && c.headerName && c.filter !== false)
        .map((c) => ({ field: c.field as string, label: c.headerName as string, colDef: c })),
    [columnDefs],
  );

  const selectedCol = filterableColumns.find((c) => c.field === condition.colId);
  const filterType = selectedCol ? detectFilterType(selectedCol.colDef) : condition.filterType;
  const operators = getOperators(filterType);
  const setValues = selectedCol ? getSetValues(selectedCol.colDef) : [];

  const handleColChange = (colId: string) => {
    if (isLocked) return;
    const col = filterableColumns.find((c) => c.field === colId);
    const ft = col ? detectFilterType(col.colDef) : 'text';
    const ops = getOperators(ft);
    onUpdate(condition.id, {
      colId,
      filterType: ft,
      operator: ft === 'set' ? 'in' : ops[0]?.value ?? 'contains',
      value: ft === 'set' ? [] : '',
      valueTo: undefined,
    });
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={[
        'flex items-start gap-1.5 rounded-lg px-2 py-2',
        isLocked ? 'bg-surface-muted/30 opacity-70 ring-1 ring-border-subtle' : 'bg-surface-muted/50',
        isDragging ? 'shadow-lg' : '',
      ].join(' ')}
    >
      {/* DnD grip */}
      <button
        type="button"
        className={`mt-1 shrink-0 touch-none text-text-subtle ${isLocked ? 'cursor-not-allowed opacity-40' : 'cursor-grab hover:text-text-secondary active:cursor-grabbing'}`}
        title="Sürükle"
        disabled={isLocked}
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-3.5 w-3.5" />
      </button>

      {/* Shift up/down */}
      <div className="mt-0.5 flex shrink-0 flex-col">
        <button
          type="button"
          onClick={() => onMove(condition.id, 'up')}
          disabled={isLocked}
          className="rounded p-0.5 text-text-subtle hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-40"
          title="Yukarı taşı"
        >
          <ChevronUp className="h-3 w-3" />
        </button>
        <button
          type="button"
          onClick={() => onMove(condition.id, 'down')}
          disabled={isLocked}
          className="rounded p-0.5 text-text-subtle hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-40"
          title="Aşağı taşı"
        >
          <ChevronDown className="h-3 w-3" />
        </button>
      </div>

      {/* Column selector */}
      <select
        className={`${SELECT_CLASS} min-w-[120px]`}
        value={condition.colId}
        disabled={isLocked}
        onChange={(e) => handleColChange(e.target.value)}
        aria-label="Filter column"
      >
        <option value="">Sütun seçin...</option>
        {filterableColumns.map((col) => (
          <option key={col.field} value={col.field}>{col.label}</option>
        ))}
      </select>

      {/* Operator selector */}
      {filterType !== 'set' && (
        <select
          className={`${SELECT_CLASS} min-w-[110px]`}
          value={condition.operator}
          disabled={isLocked}
          onChange={(e) => onUpdate(condition.id, { operator: e.target.value })}
          aria-label="Filter operator"
        >
          {operators.map((op) => (
            <option key={op.value} value={op.value}>{op.label}</option>
          ))}
        </select>
      )}

      {/* Value editor */}
      <div className="min-w-0 flex-1">
        <FilterValueEditor
          filterType={filterType}
          operator={condition.operator}
          value={condition.value}
          valueTo={condition.valueTo}
          setValues={setValues}
          disabled={isLocked}
          onChange={(val, valTo) => onUpdate(condition.id, { value: val, valueTo: valTo })}
        />
      </div>

      {/* Action buttons */}
      <div className="mt-1 flex shrink-0 items-center gap-0.5">
        {/* Clone */}
        <button
          type="button"
          onClick={() => onClone(condition.id)}
          className="rounded p-1 text-text-subtle hover:bg-surface-muted hover:text-text-secondary"
          title="Kopyala"
        >
          <Copy className="h-3.5 w-3.5" />
        </button>

        {/* Lock toggle */}
        {!parentLocked && (
          <button
            type="button"
            onClick={() => onToggleLock(condition.id)}
            className={[
              'rounded p-1 transition',
              condition.locked ? 'text-state-warning-text hover:bg-state-warning-bg' : 'text-text-subtle hover:bg-surface-muted hover:text-state-warning-text',
            ].join(' ')}
            title={condition.locked ? 'Kilidi aç' : 'Kilitle'}
          >
            {condition.locked ? <Lock className="h-3.5 w-3.5" /> : <Unlock className="h-3.5 w-3.5" />}
          </button>
        )}

        {/* Delete */}
        {canRemove && (
          <button
            type="button"
            onClick={() => onRemove(condition.id)}
            disabled={isLocked}
            className="rounded p-1 text-text-subtle hover:bg-state-danger-bg hover:text-state-danger-text disabled:cursor-not-allowed disabled:opacity-40"
            title="Koşulu sil"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
};
