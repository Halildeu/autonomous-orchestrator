import React from 'react';
import {
  createBadgeRenderer,
  createDateRenderer,
  createBooleanRenderer,
  createNumberRenderer,
  createCurrencyRenderer,
  createPercentRenderer,
} from './presets';

export default {
  title: 'Advanced/Column System/Presets',
  parameters: { layout: 'padded' },
};

const Showcase = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div className="mb-4">
    <div className="mb-1 text-xs font-semibold text-text-secondary">{label}</div>
    <div className="rounded-lg border border-border-subtle bg-surface-default p-3">
      {children}
    </div>
  </div>
);

export const BadgeRenderer = () => {
  const render = createBadgeRenderer(
    { active: 'success', inactive: 'default', pending: 'warning' },
    'default',
  );
  return (
    <div className="flex flex-col gap-3">
      <Showcase label="Badge: active">
        {render?.({ value: 'active', data: {} }) ?? '—'}
      </Showcase>
      <Showcase label="Badge: pending">
        {render?.({ value: 'pending', data: {} }) ?? '—'}
      </Showcase>
      <Showcase label="Badge: null">
        {render?.({ value: null, data: {} }) ?? '—'}
      </Showcase>
    </div>
  );
};

export const BooleanRenderer = () => {
  const render = createBooleanRenderer({ field: 'isActive', type: 'boolean' });
  return (
    <div className="flex gap-8">
      <Showcase label="true">
        {render?.({ value: true, data: {} }) ?? '—'}
      </Showcase>
      <Showcase label="false">
        {render?.({ value: false, data: {} }) ?? '—'}
      </Showcase>
    </div>
  );
};

export const NumberRenderer = () => {
  const render = createNumberRenderer({ field: 'amount', type: 'number' }, 'tr-TR');
  return (
    <Showcase label="1.234.567">
      {render?.({ value: 1234567, data: {} }) ?? '—'}
    </Showcase>
  );
};

export const CurrencyRenderer = () => {
  const render = createCurrencyRenderer({ field: 'price', type: 'currency', currency: 'TRY' }, 'tr-TR');
  return (
    <Showcase label="₺67.058">
      {render?.({ value: 67058, data: {} }) ?? '—'}
    </Showcase>
  );
};

export const PercentRenderer = () => {
  const render = createPercentRenderer({ field: 'ratio', type: 'percent' });
  return (
    <Showcase label="%85.5">
      {render?.({ value: 85.5, data: {} }) ?? '—'}
    </Showcase>
  );
};

export const DateRenderer = () => {
  const render = createDateRenderer({ field: 'date', type: 'date', dateFormat: 'short' }, 'tr-TR');
  return (
    <Showcase label="05.04.2026">
      {render?.({ value: '2026-04-05', data: {} }) ?? '—'}
    </Showcase>
  );
};
