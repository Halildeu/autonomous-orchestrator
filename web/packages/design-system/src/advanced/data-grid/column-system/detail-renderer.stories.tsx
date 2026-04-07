import React from 'react';
import { buildDetailRenderer } from './detail-renderer';
import type { ColumnMeta } from './types';

export default {
  title: 'Advanced/Column System/Detail Renderer',
  parameters: { layout: 'padded' },
};

const columns: ColumnMeta[] = [
  { field: 'name', headerName: 'Ad', type: 'bold-text' },
  { field: 'department', headerName: 'Departman', type: 'text' },
  { field: 'salary', headerName: 'Maaş', type: 'currency', currency: 'TRY' },
  { field: 'isActive', headerName: 'Aktif', type: 'boolean' },
  { field: 'startDate', headerName: 'Başlangıç', type: 'date', dateFormat: 'short' },
];

const sampleRow = {
  id: 'EMP-001',
  name: 'Ahmet Yılmaz',
  department: 'Mühendislik',
  salary: 45000,
  isActive: true,
  startDate: '2024-01-15',
};

export const WithData = () => {
  const renderer = buildDetailRenderer(columns, 'tr-TR');
  const t = (key: string) => key;
  return (
    <div className="max-w-lg rounded-xl border border-border-subtle bg-surface-default p-4">
      {renderer(sampleRow, t)}
    </div>
  );
};

export const EmptyState = () => {
  const renderer = buildDetailRenderer(columns, 'tr-TR');
  const t = (key: string) => key;
  return (
    <div className="max-w-lg rounded-xl border border-border-subtle bg-surface-default p-4">
      {renderer(null, t)}
    </div>
  );
};
