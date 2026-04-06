/**
 * Tests for gap completions:
 * - PDF export (chart-export.ts)
 * - AG Grid getSortModel (AGGridAdapter.ts)
 * - Treemap hierarchical detection (chart-type-suggestion.ts)
 * - CrossFilterChart wrapper
 */
import { describe, it, expect, vi } from 'vitest';
import { suggestChartType } from '../ai/chart-type-suggestion';
import { AGGridAdapter } from '../grid-adapter/AGGridAdapter';
import type { AGGridApi } from '../grid-adapter/AGGridAdapter';

/* ------------------------------------------------------------------ */
/*  Treemap / Sunburst Detection                                       */
/* ------------------------------------------------------------------ */

describe('suggestChartType — hierarchical detection', () => {
  it('suggests treemap for data with name + parent fields', () => {
    const data = [
      { name: 'Sales', parent: 'Root', value: 100 },
      { name: 'Online', parent: 'Sales', value: 60 },
      { name: 'Store', parent: 'Sales', value: 40 },
    ];
    const suggestions = suggestChartType(data);
    const treemap = suggestions.find(s => s.type === 'treemap');
    expect(treemap).toBeDefined();
    expect(treemap!.confidence).toBeGreaterThanOrEqual(0.7);
  });

  it('suggests sunburst as alternative to treemap', () => {
    const data = [
      { name: 'Root', parent: '', value: 200 },
      { name: 'A', parent: 'Root', value: 120 },
      { name: 'B', parent: 'Root', value: 80 },
    ];
    const suggestions = suggestChartType(data);
    const sunburst = suggestions.find(s => s.type === 'sunburst');
    expect(sunburst).toBeDefined();
  });

  it('suggests treemap for data with children arrays', () => {
    const data = [
      { name: 'Root', children: [{ name: 'A', value: 50 }], value: 50 },
    ];
    const suggestions = suggestChartType(data as Record<string, unknown>[]);
    const treemap = suggestions.find(s => s.type === 'treemap');
    expect(treemap).toBeDefined();
  });

  it('does not suggest treemap for flat data', () => {
    const data = [
      { label: 'A', value: 10 },
      { label: 'B', value: 20 },
    ];
    const suggestions = suggestChartType(data);
    const treemap = suggestions.find(s => s.type === 'treemap');
    expect(treemap).toBeUndefined();
  });
});

/* ------------------------------------------------------------------ */
/*  AG Grid getSortModel                                               */
/* ------------------------------------------------------------------ */

describe('AGGridAdapter.getSortModel', () => {
  function createMockApi(columnDefs: unknown[] = []): AGGridApi {
    return {
      setGridOption: vi.fn(),
      getFilterModel: vi.fn(() => ({})),
      setFilterModel: vi.fn(),
      getColumnDefs: vi.fn(() => columnDefs),
      getSelectedRows: vi.fn(() => []),
      forEachNode: vi.fn(),
      deselectAll: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
  }

  it('returns empty array when no columns are sorted', () => {
    const api = createMockApi([
      { field: 'name', headerName: 'Name' },
      { field: 'value', headerName: 'Value' },
    ]);
    const adapter = new AGGridAdapter('test', api);
    expect(adapter.getSortModel()).toEqual([]);
    adapter.destroy();
  });

  it('returns sort entries from column defs', () => {
    const api = createMockApi([
      { field: 'name', headerName: 'Name', sort: 'asc', sortIndex: 0 },
      { field: 'value', headerName: 'Value', sort: 'desc', sortIndex: 1 },
      { field: 'date', headerName: 'Date' },
    ]);
    const adapter = new AGGridAdapter('test', api);
    const sorts = adapter.getSortModel();
    expect(sorts).toHaveLength(2);
    expect(sorts[0]).toEqual({ field: 'name', direction: 'asc', sortIndex: 0 });
    expect(sorts[1]).toEqual({ field: 'value', direction: 'desc', sortIndex: 1 });
    adapter.destroy();
  });

  it('sorts by sortIndex', () => {
    const api = createMockApi([
      { field: 'b', sort: 'asc', sortIndex: 2 },
      { field: 'a', sort: 'desc', sortIndex: 1 },
    ]);
    const adapter = new AGGridAdapter('test', api);
    const sorts = adapter.getSortModel();
    expect(sorts[0].field).toBe('a');
    expect(sorts[1].field).toBe('b');
    adapter.destroy();
  });
});

/* ------------------------------------------------------------------ */
/*  PDF export (buildPdfFromImage)                                     */
/* ------------------------------------------------------------------ */

describe('useChartExport — PDF format', () => {
  it('exports pdf format without error', async () => {
    // We can't fully test PDF rendering in jsdom, but we verify
    // the export function handles 'pdf' format without throwing
    const { useChartExport } = await import('../collaboration/chart-export');
    const { exportChart } = useChartExport();

    // Mock a minimal ECharts instance
    const mockInstance = {
      getDataURL: vi.fn(() => {
        // Return a minimal valid 1x1 PNG data URL
        return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
      }),
    };

    // Mock URL.createObjectURL and document methods
    const mockUrl = 'blob:test';
    globalThis.URL.createObjectURL = vi.fn(() => mockUrl);
    const appendSpy = vi.spyOn(document.body, 'appendChild').mockImplementation((node) => node);
    const removeSpy = vi.spyOn(document.body, 'removeChild').mockImplementation((node) => node);

    // Should not throw
    expect(() => {
      exportChart(mockInstance, 'pdf', { filename: 'test-chart', title: 'Test' });
    }).not.toThrow();

    expect(mockInstance.getDataURL).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'png' }),
    );
    expect(globalThis.URL.createObjectURL).toHaveBeenCalled();

    appendSpy.mockRestore();
    removeSpy.mockRestore();
  });
});
