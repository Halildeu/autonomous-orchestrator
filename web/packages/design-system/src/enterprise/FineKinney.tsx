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

/** Probability values for the Fine-Kinney risk assessment method.
 * @since 1.0.0
 */
export type FineKinneyProbability = 0.1 | 0.2 | 0.5 | 1 | 3 | 6 | 10;

/** Frequency (exposure) values for the Fine-Kinney method. */
export type FineKinneyFrequency = 0.5 | 1 | 2 | 3 | 6 | 10;

/** Severity values for the Fine-Kinney method. */
export type FineKinneySeverity = 1 | 3 | 7 | 15 | 40 | 100;

/** A single risk entry in a Fine-Kinney assessment. */
export interface FineKinneyRisk {
  /** Unique identifier for this risk */
  id: string;
  /** Short hazard title */
  hazard: string;
  /** Detailed hazard description */
  description?: string;
  /** Probability factor (Olasılık) */
  probability: FineKinneyProbability;
  /** Frequency / exposure factor (Frekans / Maruz Kalma) */
  frequency: FineKinneyFrequency;
  /** Severity factor (Şiddet) */
  severity: FineKinneySeverity;
  /** Existing control measures (Mevcut Kontroller) */
  controls?: string[];
  /** Person responsible for follow-up */
  responsiblePerson?: string;
  /** Deadline date string (e.g. YYYY-MM-DD) */
  deadline?: string;
  /** Current status of the risk action */
  status?: 'open' | 'in-progress' | 'closed';
}

/** Locale text overrides for the FineKinney component. */
export interface FineKinneyLocaleText {
  /** Table column header for hazard */
  hazard: string;
  /** Table column header for probability */
  probability: string;
  /** Table column header for frequency */
  frequency: string;
  /** Table column header for severity */
  severity: string;
  /** Table column header for risk score */
  riskScore: string;
  /** Table column header for risk level */
  level: string;
  /** Table column header for controls */
  controls: string;
  /** Table column header for responsible person */
  responsible: string;
  /** Table column header for deadline */
  deadline: string;
  /** Table column header for status */
  status: string;
  /** Risk level label: acceptable */
  acceptable: string;
  /** Risk level label: notable */
  notable: string;
  /** Risk level label: significant */
  significant: string;
  /** Risk level label: high */
  high: string;
  /** Risk level label: veryHigh */
  veryHigh: string;
  /** Summary label prefix */
  totalRisks: string;
  /** Status label: open */
  statusOpen: string;
  /** Status label: in-progress */
  statusInProgress: string;
  /** Status label: closed */
  statusClosed: string;
}

/**
 * Props for the FineKinney risk assessment table.
 *
 * @see https://en.wikipedia.org/wiki/Fine%E2%80%93Kinney_method
 */
export interface FineKinneyProps extends AccessControlledProps {
  /** Array of risk items to display */
  risks: FineKinneyRisk[];
  /** Callback when a risk row is clicked */
  onRiskClick?: (risk: FineKinneyRisk) => void;
  /** Show the controls column */
  showControls?: boolean;
  /** Show the status column */
  showStatus?: boolean;
  /** Use compact row height */
  compact?: boolean;
  /** Partial locale text overrides (Turkish defaults) */
  localeText?: Partial<FineKinneyLocaleText>;
  /** Additional CSS class names */
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_LOCALE: FineKinneyLocaleText = {
  hazard: 'Tehlike',
  probability: 'Olasılık (P)',
  frequency: 'Frekans (F)',
  severity: 'Şiddet (S)',
  riskScore: 'Risk Skoru (P×F×S)',
  level: 'Seviye',
  controls: 'Kontroller',
  responsible: 'Sorumlu',
  deadline: 'Son Tarih',
  status: 'Durum',
  acceptable: 'Kabul Edilebilir',
  notable: 'Dikkate Değer',
  significant: 'Önemli',
  high: 'Yüksek',
  veryHigh: 'Çok Yüksek',
  totalRisks: 'Toplam Risk',
  statusOpen: 'Açık',
  statusInProgress: 'Devam Ediyor',
  statusClosed: 'Kapatıldı',
};

type RiskCategory = 'acceptable' | 'notable' | 'significant' | 'high' | 'veryHigh';

interface CategoryConfig {
  key: RiskCategory;
  min: number;
  max: number;
  bg: string;
  text: string;
  badge: string;
}

const CATEGORIES: CategoryConfig[] = [
  {
    key: 'acceptable',
    min: 0,
    max: 20,
    bg: 'var(--fk-acceptable-bg)',
    text: 'var(--fk-acceptable-text)',
    badge: 'var(--fk-acceptable-badge)',
  },
  {
    key: 'notable',
    min: 21,
    max: 70,
    bg: 'var(--fk-notable-bg)',
    text: 'var(--fk-notable-text)',
    badge: 'var(--fk-notable-badge)',
  },
  {
    key: 'significant',
    min: 71,
    max: 200,
    bg: 'var(--fk-significant-bg)',
    text: 'var(--fk-significant-text)',
    badge: 'var(--fk-significant-badge)',
  },
  {
    key: 'high',
    min: 201,
    max: 400,
    bg: 'var(--fk-high-bg)',
    text: 'var(--fk-high-text)',
    badge: 'var(--fk-high-badge)',
  },
  {
    key: 'veryHigh',
    min: 401,
    max: Infinity,
    bg: 'var(--fk-veryhigh-bg)',
    text: 'var(--fk-veryhigh-text)',
    badge: 'var(--fk-veryhigh-badge)',
  },
];

function getCategory(score: number): CategoryConfig {
  for (const cat of CATEGORIES) {
    if (score <= cat.max) return cat;
  }
  return CATEGORIES[CATEGORIES.length - 1];
}

function computeRiskScore(risk: FineKinneyRisk): number {
  return risk.probability * risk.frequency * risk.severity;
}

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  open: {
    bg: 'var(--fk-status-open-bg)',
    text: 'var(--fk-status-open-text)',
  },
  'in-progress': {
    bg: 'var(--fk-status-inprogress-bg)',
    text: 'var(--fk-status-inprogress-text)',
  },
  closed: {
    bg: 'var(--fk-status-closed-bg)',
    text: 'var(--fk-status-closed-text)',
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Fine-Kinney risk assessment table.
 *
 * Renders a sortable risk table with color-coded risk levels following
 * the Fine-Kinney method (Risk = Probability x Frequency x Severity).
 * Mandatory under ISG (İş Sağlığı ve Güvenliği) regulations in Turkey.
 *
 * @example
 * ```tsx
 * <FineKinney
 *   risks={[
 *     { id: '1', hazard: 'Kaygan zemin', probability: 3, frequency: 6, severity: 7 },
 *   ]}
 *   showControls
 *   showStatus
 * />
 * ```
 */
export const FineKinney: React.FC<FineKinneyProps> = ({
  risks,
  onRiskClick,
  showControls = true,
  showStatus = true,
  compact = false,
  localeText,
  className,
  access,
  accessReason,
}) => {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null;

  const t: FineKinneyLocaleText = useMemo(
    () => ({ ...DEFAULT_LOCALE, ...localeText }),
    [localeText],
  );

  // Sort by risk score descending
  const sortedRisks = useMemo(() => {
    return [...risks]
      .map((r) => ({ ...r, _score: computeRiskScore(r) }))
      .sort((a, b) => b._score - a._score);
  }, [risks]);

  // Summary counts per category
  const categoryCounts = useMemo(() => {
    const counts: Record<RiskCategory, number> = {
      acceptable: 0,
      notable: 0,
      significant: 0,
      high: 0,
      veryHigh: 0,
    };
    for (const r of sortedRisks) {
      counts[getCategory(r._score).key]++;
    }
    return counts;
  }, [sortedRisks]);

  const canInteract = !accessState.isDisabled && !accessState.isReadonly;

  const statusLabel = (status?: string): string => {
    if (status === 'open') return t.statusOpen;
    if (status === 'in-progress') return t.statusInProgress;
    if (status === 'closed') return t.statusClosed;
    return '—';
  };

  if (risks.length === 0) {
    return (
      <div
        className={cn(
          'p-8 text-center text-sm',
          'text-[var(--text-tertiary)]',
          className,
        )}
      >
        Kayıtlı risk bulunamadı
      </div>
    );
  }

  const rowPadding = compact ? 'py-1.5 px-2' : 'py-2.5 px-3';
  const fontSize = compact ? 'text-xs' : 'text-sm';

  return (
    <div
      className={cn(
        'border border-[var(--border-default)] rounded-lg bg-[var(--surface-default)] overflow-hidden',
        accessStyles(accessState.state),
        className,
      )}
      role="region"
      aria-label="Fine-Kinney risk assessment"
      data-component="fine-kinney"
      data-access-state={accessState.state}
      {...(accessState.isDisabled ? { 'aria-disabled': true } : {})}
      {...(accessReason ? { title: accessReason } : {})}
    >
      {/* ── Summary bar ── */}
      <div
        className={cn(
          'flex flex-wrap items-center gap-2 px-4 py-3',
          'border-b border-[var(--border-default)]',
          'bg-[var(--surface-subtle)]',
        )}
      >
        <span className="text-sm font-medium text-[var(--text-primary)]">
          {t.totalRisks}: {risks.length}
        </span>
        <span className="text-[var(--border-default)]">|</span>
        {CATEGORIES.map((cat) => {
          const count = categoryCounts[cat.key];
          if (count === 0) return null;
          return (
            <span
              key={cat.key}
              className="inline-flex items-center gap-1 text-xs font-medium rounded-full px-2 py-0.5"
              style={{ backgroundColor: cat.bg, color: cat.text }}
            >
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ backgroundColor: cat.badge }}
                aria-hidden="true"
              />
              {t[cat.key]}: {count}
            </span>
          );
        })}
      </div>

      {/* ── Table ── */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse" role="table">
          <thead>
            <tr className="bg-[var(--surface-subtle)]">
              <th className={cn('text-left font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)]')}>{t.hazard}</th>
              <th className={cn('text-center font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)] whitespace-nowrap')}>{t.probability}</th>
              <th className={cn('text-center font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)] whitespace-nowrap')}>{t.frequency}</th>
              <th className={cn('text-center font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)] whitespace-nowrap')}>{t.severity}</th>
              <th className={cn('text-center font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)] whitespace-nowrap')}>{t.riskScore}</th>
              <th className={cn('text-center font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)]')}>{t.level}</th>
              {showControls && (
                <th className={cn('text-left font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)]')}>{t.controls}</th>
              )}
              <th className={cn('text-left font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)]')}>{t.responsible}</th>
              <th className={cn('text-left font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)] whitespace-nowrap')}>{t.deadline}</th>
              {showStatus && (
                <th className={cn('text-center font-semibold', fontSize, rowPadding, 'text-[var(--text-primary)]')}>{t.status}</th>
              )}
            </tr>
          </thead>
          <tbody>
            {sortedRisks.map((risk) => {
              const score = risk._score;
              const cat = getCategory(score);
              const isClickable = canInteract && !!onRiskClick;
              const sts = risk.status ? STATUS_STYLES[risk.status] : undefined;

              return (
                <tr
                  key={risk.id}
                  className={cn(
                    'border-t border-[var(--border-default)]',
                    'transition-colors duration-(--motion-duration-fast)',
                    isClickable && 'cursor-pointer hover:bg-[var(--surface-hover)]',
                  )}
                  onClick={isClickable ? () => onRiskClick!(risk) : undefined}
                  role={isClickable ? 'button' : undefined}
                  tabIndex={isClickable ? 0 : undefined}
                  onKeyDown={
                    isClickable
                      ? (e: React.KeyboardEvent) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            onRiskClick!(risk);
                          }
                        }
                      : undefined
                  }
                  aria-label={isClickable ? `${risk.hazard}, risk score ${score}` : undefined}
                >
                  {/* Hazard */}
                  <td className={cn('text-left', fontSize, rowPadding)}>
                    <div className="font-medium text-[var(--text-primary)]">{risk.hazard}</div>
                    {risk.description && (
                      <div className="text-xs text-[var(--text-tertiary)] mt-0.5 line-clamp-2">
                        {risk.description}
                      </div>
                    )}
                  </td>
                  {/* P */}
                  <td className={cn('text-center tabular-nums', fontSize, rowPadding, 'text-[var(--text-secondary)]')}>
                    {risk.probability}
                  </td>
                  {/* F */}
                  <td className={cn('text-center tabular-nums', fontSize, rowPadding, 'text-[var(--text-secondary)]')}>
                    {risk.frequency}
                  </td>
                  {/* S */}
                  <td className={cn('text-center tabular-nums', fontSize, rowPadding, 'text-[var(--text-secondary)]')}>
                    {risk.severity}
                  </td>
                  {/* Score */}
                  <td className={cn('text-center tabular-nums font-bold', fontSize, rowPadding)}>
                    <span
                      className="inline-flex items-center justify-center rounded-md px-2 py-0.5 min-w-[3rem]"
                      style={{ backgroundColor: cat.bg, color: cat.text }}
                    >
                      {score}
                    </span>
                  </td>
                  {/* Level */}
                  <td className={cn('text-center', fontSize, rowPadding)}>
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap"
                      style={{ backgroundColor: cat.bg, color: cat.text }}
                    >
                      <span
                        className="inline-block w-1.5 h-1.5 rounded-full"
                        style={{ backgroundColor: cat.badge }}
                        aria-hidden="true"
                      />
                      {t[cat.key]}
                    </span>
                  </td>
                  {/* Controls */}
                  {showControls && (
                    <td className={cn('text-left', fontSize, rowPadding, 'text-[var(--text-secondary)] max-w-[200px]')}>
                      {risk.controls && risk.controls.length > 0 ? (
                        <ul className="list-disc list-inside space-y-0.5">
                          {risk.controls.map((ctrl, idx) => (
                            <li key={idx} className="truncate">{ctrl}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-[var(--text-tertiary)]">—</span>
                      )}
                    </td>
                  )}
                  {/* Responsible */}
                  <td className={cn('text-left', fontSize, rowPadding, 'text-[var(--text-secondary)] whitespace-nowrap')}>
                    {risk.responsiblePerson || '—'}
                  </td>
                  {/* Deadline */}
                  <td className={cn('text-left tabular-nums', fontSize, rowPadding, 'text-[var(--text-secondary)] whitespace-nowrap')}>
                    {risk.deadline || '—'}
                  </td>
                  {/* Status */}
                  {showStatus && (
                    <td className={cn('text-center', fontSize, rowPadding)}>
                      {risk.status ? (
                        <span
                          className="inline-block rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap"
                          style={{
                            backgroundColor: sts?.bg ?? 'transparent',
                            color: sts?.text ?? 'var(--text-secondary)',
                          }}
                        >
                          {statusLabel(risk.status)}
                        </span>
                      ) : (
                        <span className="text-[var(--text-tertiary)]">—</span>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

FineKinney.displayName = 'FineKinney';
export default FineKinney;
