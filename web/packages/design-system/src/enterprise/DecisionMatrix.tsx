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

export interface DecisionOption {
  id: string;
  name: string;
}

export interface DecisionCriterion {
  id: string;
  name: string;
  weight: number;
}

export interface DecisionScore {
  optionId: string;
  criterionId: string;
  score: number;
}

/** Props for the DecisionMatrix component.
 * @example
 * ```tsx
 * <DecisionMatrix options={[]} criteria={[]} scores={[]} />
 * ```
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/decision-matrix)
 */
export interface DecisionMatrixProps extends AccessControlledProps {
  /** Decision options (table columns) */
  options: DecisionOption[];
  /** Evaluation criteria (table rows) */
  criteria: DecisionCriterion[];
  /** Score entries linking options to criteria */
  scores: DecisionScore[];
  /** Called when a score cell value changes */
  onScoreChange?: (optionId: string, criterionId: string, score: number) => void;
  /** Maximum possible score value */
  maxScore?: number;
  /** Show weighted total row at the bottom */
  showWeightedTotals?: boolean;
  /** Highlight the winning option column */
  highlightWinner?: boolean;
  /** Optional title displayed above the matrix */
  title?: string;
  /** Additional CSS class names for the root element */
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getScoreColor(score: number, maxScore: number): { bg: string; text: string } {
  const ratio = score / maxScore;
  if (ratio >= 0.8) return { bg: 'var(--state-success-bg)', text: 'var(--state-success-text)' };
  if (ratio >= 0.6) return { bg: 'var(--state-info-bg)', text: 'var(--state-info-text)' };
  if (ratio >= 0.4) return { bg: 'var(--state-warning-bg)', text: 'var(--state-warning-text)' };
  return { bg: 'var(--state-error-bg)', text: 'var(--state-error-text)' };
}

function getScoreBarWidth(score: number, maxScore: number): string {
  return `${Math.min(100, Math.round((score / maxScore) * 100))}%`;
}

// ---------------------------------------------------------------------------
// Score cell sub-component
// ---------------------------------------------------------------------------

interface ScoreCellProps {
  score: number;
  maxScore: number;
  isWinner: boolean;
  canInteract: boolean;
  optionId: string;
  criterionId: string;
  onScoreChange?: (optionId: string, criterionId: string, score: number) => void;
}

const ScoreCell: React.FC<ScoreCellProps> = ({
  score,
  maxScore,
  isWinner,
  canInteract,
  optionId,
  criterionId,
  onScoreChange,
}) => {
  const color = getScoreColor(score, maxScore);
  const barWidth = getScoreBarWidth(score, maxScore);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!canInteract || !onScoreChange) return;
      if (e.key === 'ArrowUp' && score < maxScore) {
        e.preventDefault();
        onScoreChange(optionId, criterionId, score + 1);
      } else if (e.key === 'ArrowDown' && score > 0) {
        e.preventDefault();
        onScoreChange(optionId, criterionId, score - 1);
      }
    },
    [canInteract, onScoreChange, optionId, criterionId, score, maxScore],
  );

  const isEditable = canInteract && !!onScoreChange;

  return (
    <td
      className={cn(
        'py-2 px-3 text-center relative',
        isWinner && 'bg-[var(--state-success-bg)]',
      )}
      role={isEditable ? 'gridcell' : undefined}
      tabIndex={isEditable ? 0 : undefined}
      onKeyDown={isEditable ? handleKeyDown : undefined}
      aria-label={`${score} out of ${maxScore}`}
    >
      {/* Score bar background */}
      <div
        className="absolute inset-y-0 left-0 opacity-20 transition-all duration-(--motion-duration-medium)"
        style={{ width: barWidth, backgroundColor: color.text }}
      />
      {/* Score value */}
      <span className="relative z-10 text-sm font-mono font-medium" style={{ color: color.text }}>
        {score}
      </span>
    </td>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/** Weighted scoring decision matrix table for comparing alternatives against criteria. */
export function DecisionMatrix({
  options,
  criteria,
  scores,
  onScoreChange,
  maxScore = 10,
  showWeightedTotals = true,
  highlightWinner = true,
  title,
  className,
  access,
  accessReason,
}: DecisionMatrixProps) {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null;

  const canInteract = !accessState.isDisabled && !accessState.isReadonly;

  // Build score lookup
  const scoreMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of scores) {
      map.set(`${s.optionId}:${s.criterionId}`, s.score);
    }
    return map;
  }, [scores]);

  // Calculate weighted totals per option
  const weightedTotals = useMemo(() => {
    const totals = new Map<string, number>();
    const totalWeight = criteria.reduce((sum, c) => sum + c.weight, 0);

    for (const option of options) {
      let weightedSum = 0;
      for (const criterion of criteria) {
        const rawScore = scoreMap.get(`${option.id}:${criterion.id}`) ?? 0;
        const normalizedWeight = totalWeight > 0 ? criterion.weight / totalWeight : 0;
        weightedSum += rawScore * normalizedWeight;
      }
      totals.set(option.id, Math.round(weightedSum * 100) / 100);
    }
    return totals;
  }, [options, criteria, scoreMap]);

  // Find winner
  const winnerId = useMemo(() => {
    if (!highlightWinner) return null;
    let maxTotal = -Infinity;
    let winner: string | null = null;
    for (const [optId, total] of weightedTotals) {
      if (total > maxTotal) {
        maxTotal = total;
        winner = optId;
      }
    }
    return winner;
  }, [weightedTotals, highlightWinner]);

  // Total weight for display
  const totalWeight = useMemo(() => criteria.reduce((sum, c) => sum + c.weight, 0), [criteria]);

  return (
    <div
      className={cn(
        'border border-border-default rounded-lg bg-surface-default overflow-hidden',
        accessStyles(accessState.state),
        className,
      )}
      data-component="decision-matrix"
      data-access-state={accessState.state}
      role="table"
      aria-label={title ?? 'Decision Matrix'}
      {...(accessState.isDisabled ? { 'aria-disabled': true } : {})}
      {...(accessReason ? { title: accessReason } : {})}
    >
      {/* Title */}
      {title && (
        <div className="px-4 py-3 border-b border-border-default">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-surface-muted border-b border-border-default">
              <th className="py-2.5 px-3 text-left text-xs font-semibold text-text-secondary uppercase tracking-wide">
                Criteria
              </th>
              <th className="py-2.5 px-3 text-center text-xs font-semibold text-text-secondary uppercase tracking-wide w-20">
                Weight
              </th>
              {options.map((option) => (
                <th
                  key={option.id}
                  className={cn(
                    'py-2.5 px-3 text-center text-xs font-semibold uppercase tracking-wide min-w-[80px]',
                    highlightWinner && option.id === winnerId
                      ? 'text-[var(--state-success-text)] bg-[var(--state-success-bg)]'
                      : 'text-text-secondary',
                  )}
                >
                  <div className="flex flex-col items-center gap-0.5">
                    <span>{option.name}</span>
                    {highlightWinner && option.id === winnerId && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[var(--state-success-text)] text-[var(--text-inverse)] font-bold">
                        WINNER
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {criteria.map((criterion) => {
              const weightPercent = totalWeight > 0 ? Math.round((criterion.weight / totalWeight) * 100) : 0;
              return (
                <tr
                  key={criterion.id}
                  className="border-b border-border-subtle transition-colors hover:bg-surface-muted"
                >
                  <td className="py-2 px-3 text-sm text-text-primary">{criterion.name}</td>
                  <td className="py-2 px-3 text-center">
                    <span className="text-xs font-mono text-text-secondary">
                      {criterion.weight}
                    </span>
                    <span className="text-[10px] text-text-tertiary ml-1">
                      ({weightPercent}%)
                    </span>
                  </td>
                  {options.map((option) => {
                    const score = scoreMap.get(`${option.id}:${criterion.id}`) ?? 0;
                    return (
                      <ScoreCell
                        key={`${option.id}-${criterion.id}`}
                        score={score}
                        maxScore={maxScore}
                        isWinner={highlightWinner && option.id === winnerId}
                        canInteract={canInteract}
                        optionId={option.id}
                        criterionId={criterion.id}
                        onScoreChange={onScoreChange}
                      />
                    );
                  })}
                </tr>
              );
            })}
          </tbody>

          {/* Weighted totals footer */}
          {showWeightedTotals && (
            <tfoot>
              <tr className="bg-surface-muted border-t-2 border-border-default">
                <td className="py-3 px-3 text-sm font-bold text-text-primary">
                  Weighted Total
                </td>
                <td className="py-3 px-3 text-center text-xs font-mono text-text-secondary font-bold">
                  {totalWeight}
                </td>
                {options.map((option) => {
                  const total = weightedTotals.get(option.id) ?? 0;
                  const isWin = highlightWinner && option.id === winnerId;
                  return (
                    <td
                      key={option.id}
                      className={cn(
                        'py-3 px-3 text-center font-mono text-sm font-bold',
                        isWin
                          ? 'text-[var(--state-success-text)] bg-[var(--state-success-bg)]'
                          : 'text-text-primary',
                      )}
                    >
                      {total.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}

DecisionMatrix.displayName = 'DecisionMatrix';
export default DecisionMatrix;
