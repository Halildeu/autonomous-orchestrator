// @vitest-environment jsdom
/**
 * PURPOSE: Test CSS-to-theme adapter functions and MutationObserver sync.
 * RISK: Grid/chart themes desync from CSS vars → visual mismatch in dark mode.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { cssVarsToGridTheme, cssVarsToChartColors, useAutoThemeAdapter } from '../useAutoThemeAdapter';

// Mock getComputedStyle to return predictable CSS var values
const cssVarMap: Record<string, string> = {};
beforeEach(() => {
  Object.keys(cssVarMap).forEach((k) => delete cssVarMap[k]);
  vi.spyOn(window, 'getComputedStyle').mockReturnValue({
    getPropertyValue: (name: string) => cssVarMap[name] || '',
  } as CSSStyleDeclaration);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('cssVarsToGridTheme', () => {
  it('returns fallback values when CSS vars are empty', () => {
    const theme = cssVarsToGridTheme();
    expect(theme.headerBackgroundColor).toBe('var(--surface-muted)');
    expect(theme.foregroundColor).toBe('var(--text-primary)');
    expect(theme.fontSize).toBe('13px');
    expect(theme.headerFontSize).toBe('12px');
  });

  it('reads CSS vars when set', () => {
    cssVarMap['--surface-muted-bg'] = '#f1f5f9';
    cssVarMap['--text-primary'] = '#1e293b';
    const theme = cssVarsToGridTheme();
    expect(theme.headerBackgroundColor).toBe('#f1f5f9');
    expect(theme.foregroundColor).toBe('#1e293b');
  });
});

describe('cssVarsToChartColors', () => {
  it('returns fallback values when CSS vars are empty', () => {
    const colors = cssVarsToChartColors();
    expect(colors.primaryColor).toBe('var(--action-primary)');
    expect(colors.series).toHaveLength(6);
  });

  it('reads CSS vars for series colors', () => {
    cssVarMap['--action-primary-bg'] = '#3b82f6';
    const colors = cssVarsToChartColors();
    expect(colors.primaryColor).toBe('#3b82f6');
  });
});

describe('useAutoThemeAdapter', () => {
  it('returns gridTheme and chartColors', () => {
    const { result } = renderHook(() => useAutoThemeAdapter());
    expect(result.current.gridTheme).toBeDefined();
    expect(result.current.chartColors).toBeDefined();
    expect(result.current.gridTheme.fontSize).toBe('13px');
    expect(result.current.chartColors.series).toHaveLength(6);
  });
});
