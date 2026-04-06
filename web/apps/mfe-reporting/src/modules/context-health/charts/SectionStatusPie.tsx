import React from 'react';
import { PieChart } from '@mfe/x-charts';
import type { ChartDataRow } from '../types';

const COLORS: Record<string, string> = {
  OK: '#10b981',
  WARN: '#f59e0b',
  FAIL: '#ef4444',
  IDLE: '#9ca3af',
};

type Props = { data: ChartDataRow[] };

const SectionStatusPie: React.FC<Props> = ({ data }) => (
  <PieChart
    data={data.map((d) => ({
      label: d.label,
      value: d.value as number,
      color: COLORS[d.label] ?? '#6b7280',
    }))}
    showLegend
    showPercentage
    size="md"
  />
);

export default SectionStatusPie;
