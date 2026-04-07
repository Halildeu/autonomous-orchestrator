// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import {
  createBadgeRenderer,
  createDateRenderer,
  createBooleanRenderer,
  createNumberRenderer,
  createCurrencyRenderer,
  createBoldTextRenderer,
  createPercentRenderer,
  createLinkRenderer,
  createTextRenderer,
} from '../presets';

afterEach(() => {
  cleanup();
});

describe('column-presets — contract', () => {
  describe('createTextRenderer', () => {
    it('returns undefined (AG Grid default is fine)', () => {
      expect(createTextRenderer()).toBeUndefined();
    });
  });

  describe('createBoldTextRenderer', () => {
    it('renders value with font-semibold class', () => {
      const renderer = createBoldTextRenderer()!;
      const result = renderer({ value: 'John Doe', data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('John Doe');
      expect(container.querySelector('.font-semibold')).toBeTruthy();
    });

    it('renders dash for null value', () => {
      const renderer = createBoldTextRenderer()!;
      const result = renderer({ value: null, data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('-');
    });
  });

  describe('createBadgeRenderer', () => {
    it('renders Badge with correct variant from variantMap', () => {
      const renderer = createBadgeRenderer(
        { ACTIVE: 'success', INACTIVE: 'error' },
        'default',
      );

      const result = renderer({ value: 'ACTIVE', data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('ACTIVE');
    });

    it('uses default variant for unknown values', () => {
      const renderer = createBadgeRenderer(
        { ACTIVE: 'success' },
        'warning',
      );

      const result = renderer({ value: 'UNKNOWN', data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('UNKNOWN');
    });

    it('renders dash for empty/null value', () => {
      const renderer = createBadgeRenderer(
        { ACTIVE: 'success' },
        'default',
      );

      const result = renderer({ value: null, data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('-');
    });

    it('applies label map with translation function', () => {
      const t = (key: string) => key === 'status.active' ? 'Aktif' : key;
      const renderer = createBadgeRenderer(
        { ACTIVE: 'success' },
        'default',
        { ACTIVE: 'status.active' },
        t,
      );

      const result = renderer({ value: 'ACTIVE', data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('Aktif');
    });

    it('applies label map without translation function (raw labels)', () => {
      const renderer = createBadgeRenderer(
        { ACTIVE: 'success' },
        'default',
        { ACTIVE: 'Aktif' },
      );

      const result = renderer({ value: 'ACTIVE', data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('Aktif');
    });
  });

  describe('createDateRenderer', () => {
    it('formats date with short format', () => {
      const renderer = createDateRenderer({ format: 'short' }, 'en-US');
      const result = renderer({ value: '2024-06-15T12:00:00Z', data: undefined });
      // Should contain some date string (locale-dependent)
      expect(typeof result).toBe('string');
      expect(String(result)).toContain('2024');
    });

    it('renders empty text for null value', () => {
      const renderer = createDateRenderer({ format: 'short' }, 'en-US');
      const result = renderer({ value: null, data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('-');
    });

    it('renders custom empty text', () => {
      const renderer = createDateRenderer({ format: 'short', emptyText: 'N/A' }, 'en-US');
      const result = renderer({ value: '', data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('N/A');
    });

    it('handles invalid date gracefully', () => {
      const renderer = createDateRenderer({ format: 'short' }, 'en-US');
      const result = renderer({ value: 'not-a-date', data: undefined });
      const { container } = render(<>{result}</>);
      // Should show empty text for NaN date
      expect(container.textContent).toBe('-');
    });
  });

  describe('createBooleanRenderer', () => {
    it('renders checkmark icon for true value', () => {
      const t = (key: string) => key;
      const renderer = createBooleanRenderer({ display: 'icon' }, t);

      const result = renderer({ value: true, data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toContain('✓');
    });

    it('renders X icon for false value', () => {
      const t = (key: string) => key;
      const renderer = createBooleanRenderer({ display: 'icon' }, t);

      const result = renderer({ value: false, data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toContain('✗');
    });

    it('renders text labels for true/false in text mode', () => {
      const t = (key: string) => key;
      const renderer = createBooleanRenderer(
        { display: 'text', trueLabel: 'Yes', falseLabel: 'No' },
        t,
      );

      expect(renderer({ value: true, data: undefined })).toBe('Yes');
      expect(renderer({ value: false, data: undefined })).toBe('No');
    });

    it('treats "true" string and 1 as truthy', () => {
      const t = (key: string) => key;
      const renderer = createBooleanRenderer({ display: 'icon' }, t);

      const result1 = renderer({ value: 'true', data: undefined });
      const { container: c1 } = render(<>{result1}</>);
      expect(c1.textContent).toContain('✓');

      const result2 = renderer({ value: 1, data: undefined });
      const { container: c2 } = render(<>{result2}</>);
      expect(c2.textContent).toContain('✓');
    });
  });

  describe('createNumberRenderer', () => {
    it('formats number with locale and decimals', () => {
      const renderer = createNumberRenderer({ decimals: 2 }, 'en-US');
      const result = renderer({ value: 1234.5, data: undefined });
      expect(String(result)).toContain('1,234.50');
    });

    it('renders prefix and suffix', () => {
      const renderer = createNumberRenderer({ prefix: '$', suffix: 'USD', decimals: 0 }, 'en-US');
      const result = renderer({ value: 100, data: undefined });
      expect(String(result)).toContain('$');
      expect(String(result)).toContain('USD');
    });

    it('renders dash for null value', () => {
      const renderer = createNumberRenderer({ decimals: 0 }, 'en-US');
      const result = renderer({ value: null, data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('-');
    });

    it('renders dash for non-finite number', () => {
      const renderer = createNumberRenderer({ decimals: 0 }, 'en-US');
      const result = renderer({ value: NaN, data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('-');
    });
  });

  describe('createCurrencyRenderer', () => {
    it('formats currency with locale', () => {
      const renderer = createCurrencyRenderer({ currencyCode: 'USD', decimals: 2 }, 'en-US');
      const result = renderer({ value: 1500.99, data: undefined });
      const str = String(result);
      expect(str).toContain('1,500.99');
    });

    it('renders dash for null value', () => {
      const renderer = createCurrencyRenderer({ currencyCode: 'TRY' }, 'tr-TR');
      const result = renderer({ value: null, data: undefined });
      const { container } = render(<>{result}</>);
      expect(container.textContent).toBe('-');
    });
  });

  describe('createPercentRenderer', () => {
    it('formats percentage with decimals', () => {
      const renderer = createPercentRenderer({ decimals: 1, showBar: false });
      const result = renderer({ value: 75.5, data: undefined });
      expect(String(result)).toBe('%75.5');
    });

    it('renders with progress bar when showBar is true', () => {
      const renderer = createPercentRenderer({ decimals: 0, showBar: true });
      const result = renderer({ value: 50, data: undefined });
      const { container } = render(<>{result}</>);
      // Should have a bar div with width style
      const bar = container.querySelector('[style]');
      expect(bar).toBeTruthy();
    });
  });

  describe('createLinkRenderer', () => {
    it('renders anchor with href from value', () => {
      const renderer = createLinkRenderer({ newTab: false });
      const result = renderer({ value: 'https://example.com', data: undefined });
      const { container } = render(<>{result}</>);
      const link = container.querySelector('a');
      expect(link).toHaveAttribute('href', 'https://example.com');
    });

    it('opens in new tab when newTab is true', () => {
      const renderer = createLinkRenderer({ newTab: true });
      const result = renderer({ value: 'https://example.com', data: undefined });
      const { container } = render(<>{result}</>);
      const link = container.querySelector('a');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('uses hrefField from row data', () => {
      const renderer = createLinkRenderer({ hrefField: 'url' });
      const result = renderer({ value: 'Click Me', data: { url: '/details/123' } as Record<string, unknown> });
      const { container } = render(<>{result}</>);
      const link = container.querySelector('a');
      expect(link).toHaveAttribute('href', '/details/123');
      expect(link?.textContent).toBe('Click Me');
    });
  });
});
