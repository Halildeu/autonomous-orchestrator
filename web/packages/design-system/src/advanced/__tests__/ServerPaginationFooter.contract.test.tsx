// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { ServerPaginationFooter } from '../data-grid/ServerPaginationFooter';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function createMockGridApi(overrides: Record<string, unknown> = {}) {
  let paginationChangedHandler: (() => void) | null = null;

  const api = {
    paginationGetCurrentPage: vi.fn(() => 2),
    paginationGetTotalPages: vi.fn(() => 10),
    paginationGetPageSize: vi.fn(() => 20),
    paginationGetRowCount: vi.fn(() => 200),
    paginationGoToPage: vi.fn(),
    setGridOption: vi.fn(),
    addEventListener: vi.fn((event: string, handler: () => void) => {
      if (event === 'paginationChanged') {
        paginationChangedHandler = handler;
      }
    }),
    removeEventListener: vi.fn(),
    // Helper to trigger pagination change
    _triggerPaginationChanged: () => paginationChangedHandler?.(),
    ...overrides,
  };

  return api as unknown as import('ag-grid-community').GridApi & { _triggerPaginationChanged: () => void };
}

describe('ServerPaginationFooter — contract', () => {
  it('renders nothing when gridApi is null', () => {
    const { container } = render(
      <ServerPaginationFooter gridApi={null} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('displays correct row range info', () => {
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    // Page 2 (0-indexed), pageSize 20, total 200
    // startRow = 2*20+1 = 41, endRow = min(3*20, 200) = 60
    expect(screen.getByText(/41 – 60 \/ 200/)).toBeInTheDocument();
  });

  it('displays "Kayit yok" when totalRows is 0', () => {
    const gridApi = createMockGridApi({
      paginationGetRowCount: vi.fn(() => 0),
      paginationGetCurrentPage: vi.fn(() => 0),
      paginationGetTotalPages: vi.fn(() => 0),
    });

    render(<ServerPaginationFooter gridApi={gridApi} />);
    expect(screen.getByText('Kayıt yok')).toBeInTheDocument();
  });

  it('navigates to next page when next button clicked', async () => {
    const user = userEvent.setup();
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    const nextBtn = screen.getByLabelText('Sonraki sayfa');
    await user.click(nextBtn);
    expect(gridApi.paginationGoToPage).toHaveBeenCalledWith(3);
  });

  it('navigates to previous page when prev button clicked', async () => {
    const user = userEvent.setup();
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    const prevBtn = screen.getByLabelText('Önceki sayfa');
    await user.click(prevBtn);
    expect(gridApi.paginationGoToPage).toHaveBeenCalledWith(1);
  });

  it('navigates to first page when first button clicked', async () => {
    const user = userEvent.setup();
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    const firstBtn = screen.getByLabelText('İlk sayfa');
    await user.click(firstBtn);
    expect(gridApi.paginationGoToPage).toHaveBeenCalledWith(0);
  });

  it('navigates to last page when last button clicked', async () => {
    const user = userEvent.setup();
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    const lastBtn = screen.getByLabelText('Son sayfa');
    await user.click(lastBtn);
    expect(gridApi.paginationGoToPage).toHaveBeenCalledWith(9);
  });

  it('disables prev/first buttons on first page', () => {
    const gridApi = createMockGridApi({
      paginationGetCurrentPage: vi.fn(() => 0),
    });

    render(<ServerPaginationFooter gridApi={gridApi} />);

    expect(screen.getByLabelText('İlk sayfa')).toBeDisabled();
    expect(screen.getByLabelText('Önceki sayfa')).toBeDisabled();
  });

  it('disables next/last buttons on last page', () => {
    const gridApi = createMockGridApi({
      paginationGetCurrentPage: vi.fn(() => 9),
    });

    render(<ServerPaginationFooter gridApi={gridApi} />);

    expect(screen.getByLabelText('Sonraki sayfa')).toBeDisabled();
    expect(screen.getByLabelText('Son sayfa')).toBeDisabled();
  });

  it('shows editable page input with correct current page (1-indexed)', () => {
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    const input = screen.getByLabelText('Sayfa numarası') as HTMLInputElement;
    expect(input.value).toBe('3'); // page index 2 => display "3"
  });

  it('navigates to typed page on Enter key', async () => {
    const user = userEvent.setup();
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    const input = screen.getByLabelText('Sayfa numarası');
    await user.clear(input);
    await user.type(input, '7');
    await user.keyboard('{Enter}');

    expect(gridApi.paginationGoToPage).toHaveBeenCalledWith(6); // 7 - 1 = 6 (0-indexed)
  });

  it('shows total pages next to input', () => {
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    expect(screen.getByText('/ 10')).toBeInTheDocument();
  });

  it('renders page size selector with default options', () => {
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    const select = screen.getByRole('combobox');
    const options = Array.from(select.querySelectorAll('option'));
    const values = options.map((o) => o.value);
    expect(values).toContain('25');
    expect(values).toContain('50');
    expect(values).toContain('100');
    expect(values).toContain('200');
  });

  it('renders "Tumu" option when showAllOption is true', () => {
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} showAllOption={true} />);

    const select = screen.getByRole('combobox');
    const options = Array.from(select.querySelectorAll('option'));
    const labels = options.map((o) => o.textContent);
    expect(labels).toContain('Tümü');
  });

  it('calls setGridOption when page size changed', async () => {
    const user = userEvent.setup();
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    const select = screen.getByRole('combobox');
    await user.selectOptions(select, '100');
    expect(gridApi.setGridOption).toHaveBeenCalledWith('paginationPageSize', 100);
  });

  it('listens to paginationChanged event on mount', () => {
    const gridApi = createMockGridApi();

    render(<ServerPaginationFooter gridApi={gridApi} />);

    expect(gridApi.addEventListener).toHaveBeenCalledWith('paginationChanged', expect.any(Function));
  });

  it('renders startSlot content', () => {
    const gridApi = createMockGridApi();

    render(
      <ServerPaginationFooter
        gridApi={gridApi}
        startSlot={<span data-testid="start-slot">Mode: Server</span>}
      />,
    );

    expect(screen.getByTestId('start-slot')).toBeInTheDocument();
  });

  it('has correct data-component attribute for testing', () => {
    const gridApi = createMockGridApi();

    const { container } = render(<ServerPaginationFooter gridApi={gridApi} />);

    expect(container.querySelector('[data-component="server-pagination-footer"]')).toBeInTheDocument();
  });
});
