// @vitest-environment jsdom
/**
 * PURPOSE: Verify theme controller state management, persistence, and DOM sync.
 * RISK: Theme changes not persisted → user loses preferences on refresh.
 *       DOM attributes not synced → dark mode / density / radius breaks.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getThemeAxes,
  updateThemeAxes,
  subscribeThemeAxes,
  setAppearance,
  setDensity,
  setRadius,
  setElevation,
  setMotion,
  setContrastRatio,
  setOverlayIntensity,
  setOverlayOpacity,
  THEME_APPEARANCE_OPTIONS,
  THEME_DENSITY_OPTIONS,
  THEME_RADIUS_OPTIONS,
  THEME_ELEVATION_OPTIONS,
  THEME_MOTION_OPTIONS,
} from '../theme-controller';

beforeEach(() => {
  localStorage.clear();
  // Reset DOM attributes
  document.documentElement.removeAttribute('data-appearance');
  document.documentElement.removeAttribute('data-density');
  document.documentElement.removeAttribute('data-mode');
});

describe('getThemeAxes', () => {
  it('returns a valid axes object with all required keys', () => {
    const axes = getThemeAxes();
    expect(axes).toHaveProperty('appearance');
    expect(axes).toHaveProperty('density');
    expect(axes).toHaveProperty('radius');
    expect(axes).toHaveProperty('elevation');
    expect(axes).toHaveProperty('motion');
    expect(axes).toHaveProperty('contrastRatio');
  });
});

describe('updateThemeAxes', () => {
  it('merges partial patch into current axes', () => {
    updateThemeAxes({ density: 'compact' });
    expect(getThemeAxes().density).toBe('compact');
  });

  it('sets data-attribute on document.documentElement', () => {
    updateThemeAxes({ appearance: 'dark' });
    expect(document.documentElement.getAttribute('data-appearance')).toBe('dark');
  });

  it('persists to localStorage', () => {
    updateThemeAxes({ radius: 'sharp' });
    const stored = JSON.parse(localStorage.getItem('themeAxes') || '{}');
    expect(stored.radius).toBe('sharp');
  });

  it('clamps overlayIntensity to 0-60', () => {
    updateThemeAxes({ overlayIntensity: 100 });
    expect(getThemeAxes().overlayIntensity).toBeLessThanOrEqual(60);
  });

  it('clamps overlayOpacity to 0-100', () => {
    updateThemeAxes({ overlayOpacity: -10 });
    expect(getThemeAxes().overlayOpacity).toBeGreaterThanOrEqual(0);
  });
});

describe('subscribeThemeAxes', () => {
  it('calls listener on update', () => {
    const listener = vi.fn();
    const unsubscribe = subscribeThemeAxes(listener);
    listener.mockClear(); // Clear any initial calls
    updateThemeAxes({ radius: 'sharp' });
    expect(listener).toHaveBeenCalled();
    expect(listener).toHaveBeenCalledWith(expect.objectContaining({ radius: 'sharp' }));
    unsubscribe();
  });

  it('unsubscribe stops further notifications', () => {
    const listener = vi.fn();
    const unsub = subscribeThemeAxes(listener);
    unsub();
    listener.mockClear();
    updateThemeAxes({ radius: 'rounded' });
    expect(listener).not.toHaveBeenCalled();
  });
});

describe('convenience setters', () => {
  it('setAppearance updates appearance axis', () => {
    setAppearance('dark');
    expect(getThemeAxes().appearance).toBe('dark');
  });

  it('setDensity updates density axis', () => {
    setDensity('compact');
    expect(getThemeAxes().density).toBe('compact');
  });

  it('setRadius updates radius axis', () => {
    setRadius('sharp');
    expect(getThemeAxes().radius).toBe('sharp');
  });

  it('setElevation updates elevation axis', () => {
    setElevation('flat');
    expect(getThemeAxes().elevation).toBe('flat');
  });

  it('setMotion updates motion axis', () => {
    setMotion('reduced');
    expect(getThemeAxes().motion).toBe('reduced');
  });

  it('setContrastRatio updates contrastRatio axis', () => {
    setContrastRatio('aaa');
    expect(getThemeAxes().contrastRatio).toBe('aaa');
  });

  it('setOverlayIntensity updates overlayIntensity', () => {
    setOverlayIntensity(30);
    expect(getThemeAxes().overlayIntensity).toBe(30);
  });

  it('setOverlayOpacity updates overlayOpacity', () => {
    setOverlayOpacity(50);
    expect(getThemeAxes().overlayOpacity).toBe(50);
  });
});

describe('option constants', () => {
  it('THEME_APPEARANCE_OPTIONS includes light and dark', () => {
    expect(THEME_APPEARANCE_OPTIONS).toContain('light');
    expect(THEME_APPEARANCE_OPTIONS).toContain('dark');
  });

  it('THEME_DENSITY_OPTIONS has at least 2 modes', () => {
    expect(THEME_DENSITY_OPTIONS).toContain('comfortable');
    expect(THEME_DENSITY_OPTIONS).toContain('compact');
    expect(THEME_DENSITY_OPTIONS.length).toBeGreaterThanOrEqual(2);
  });

  it('THEME_RADIUS_OPTIONS has 2 modes', () => {
    expect(THEME_RADIUS_OPTIONS).toEqual(['rounded', 'sharp']);
  });

  it('THEME_ELEVATION_OPTIONS has 2 modes', () => {
    expect(THEME_ELEVATION_OPTIONS).toEqual(['raised', 'flat']);
  });

  it('THEME_MOTION_OPTIONS has 2 modes', () => {
    expect(THEME_MOTION_OPTIONS).toEqual(['standard', 'reduced']);
  });
});
