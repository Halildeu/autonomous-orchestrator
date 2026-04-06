// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { buildDetailRenderer } from '../detail-renderer';
import type { ColumnMeta } from '../types';

afterEach(() => {
  cleanup();
});

const t = (key: string) => {
  const map: Record<string, string> = {
    'users.columns.name': 'Full Name',
    'users.columns.role': 'Role',
    'users.columns.status': 'Status',
    'users.columns.age': 'Age',
    'users.columns.salary': 'Salary',
    'users.columns.active': 'Active',
    'users.columns.date': 'Created',
    'shared.status.active': 'Aktif',
    'reports.detail.empty': 'Select a row to see details.',
  };
  return map[key] ?? key;
};

const sampleColumns: ColumnMeta[] = [
  { field: 'name', headerNameKey: 'users.columns.name', columnType: 'bold-text' },
  {
    field: 'role',
    headerNameKey: 'users.columns.role',
    columnType: 'badge',
    variantMap: { ADMIN: 'danger', USER: 'default' },
  },
  {
    field: 'status',
    headerNameKey: 'users.columns.status',
    columnType: 'status',
    statusMap: { ACTIVE: { variant: 'success', labelKey: 'shared.status.active' } },
  },
  {
    field: 'age',
    headerNameKey: 'users.columns.age',
    columnType: 'number',
    decimals: 0,
  },
  {
    field: 'salary',
    headerNameKey: 'users.columns.salary',
    columnType: 'currency',
    currencyCode: 'TRY',
    decimals: 2,
  },
  {
    field: 'active',
    headerNameKey: 'users.columns.active',
    columnType: 'boolean',
    trueLabel: 'Yes',
    falseLabel: 'No',
    display: 'text',
  },
  {
    field: 'createdAt',
    headerNameKey: 'users.columns.date',
    columnType: 'date',
    format: 'short',
  },
];

describe('column-detail-renderer — contract', () => {
  it('renders null/empty row with empty state message', () => {
    const renderDetail = buildDetailRenderer(sampleColumns);
    const result = renderDetail(null, t);

    render(<>{result}</>);
    expect(screen.getByText('Select a row to see details.')).toBeInTheDocument();
  });

  it('renders all column fields as label-value pairs', () => {
    const renderDetail = buildDetailRenderer(sampleColumns, 'en-US');
    const row = {
      name: 'John Doe',
      role: 'ADMIN',
      status: 'ACTIVE',
      age: 30,
      salary: 5000,
      active: true,
      createdAt: '2024-01-15T00:00:00Z',
    };

    const result = renderDetail(row, t);
    render(<>{result}</>);

    // Labels (from translation function)
    expect(screen.getByText('Full Name')).toBeInTheDocument();
    expect(screen.getByText('Role')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Age')).toBeInTheDocument();
    expect(screen.getByText('Salary')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();

    // Values
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('ADMIN')).toBeInTheDocument();
    expect(screen.getByText('Aktif')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
  });

  it('renders dash for null field values', () => {
    const renderDetail = buildDetailRenderer(sampleColumns, 'en-US');
    const row = {
      name: null,
      role: '',
      status: null,
      age: null,
      salary: null,
      active: null,
      createdAt: null,
    };

    const result = renderDetail(row as unknown as Record<string, unknown>, t);
    const { container } = render(<>{result}</>);

    // All null values should render "-"
    const dashes = container.querySelectorAll('.text-text-subtle');
    expect(dashes.length).toBeGreaterThan(0);
  });

  it('shows row.id when present but not in column definitions', () => {
    const renderDetail = buildDetailRenderer(sampleColumns, 'en-US');
    const row = {
      id: 'ROW-42',
      name: 'Jane',
      role: 'USER',
      status: 'ACTIVE',
      age: 25,
      salary: 3000,
      active: true,
      createdAt: '2024-06-01',
    };

    const result = renderDetail(row, t);
    render(<>{result}</>);

    expect(screen.getByText('ID')).toBeInTheDocument();
    expect(screen.getByText('ROW-42')).toBeInTheDocument();
  });

  it('renders extra fields after column-based fields', () => {
    const renderDetail = buildDetailRenderer(
      [{ field: 'name', headerNameKey: 'users.columns.name', columnType: 'text' }],
      'en-US',
      [{ label: 'Notes', field: 'notes' }],
    );

    const row = { name: 'Test', notes: 'Some important note' };
    const result = renderDetail(row, t);
    render(<>{result}</>);

    expect(screen.getByText('Notes')).toBeInTheDocument();
    expect(screen.getByText('Some important note')).toBeInTheDocument();
  });

  it('hides columns with hidden=true', () => {
    const columns: ColumnMeta[] = [
      { field: 'visible', headerNameKey: 'Visible', columnType: 'text' },
      { field: 'hidden', headerNameKey: 'Hidden', columnType: 'text', hidden: true },
    ];

    const renderDetail = buildDetailRenderer(columns, 'en-US');
    const row = { visible: 'Show', hidden: 'Hide' };
    const result = renderDetail(row, t);
    render(<>{result}</>);

    expect(screen.getByText('Visible')).toBeInTheDocument();
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument();
  });

  it('formats boolean field correctly', () => {
    const columns: ColumnMeta[] = [
      {
        field: 'active',
        headerNameKey: 'Active',
        columnType: 'boolean',
        trueLabel: 'Evet',
        falseLabel: 'Hayir',
        display: 'text',
      },
    ];

    const renderDetail = buildDetailRenderer(columns, 'tr-TR');

    const trueResult = renderDetail({ active: true }, t);
    const { container: c1 } = render(<>{trueResult}</>);
    expect(c1.textContent).toContain('Evet');

    cleanup();

    const falseResult = renderDetail({ active: false }, t);
    const { container: c2 } = render(<>{falseResult}</>);
    expect(c2.textContent).toContain('Hayir');
  });
});
