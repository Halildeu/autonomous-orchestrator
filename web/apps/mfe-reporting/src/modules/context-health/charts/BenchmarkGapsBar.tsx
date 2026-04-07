import React from 'react';
import { BarChart } from '@mfe/x-charts';
import type { ChartDataRow } from '../types';

type Props = { data: ChartDataRow[] };

const BenchmarkGapsBar: React.FC<Props> = ({ data }) => (
  <BarChart
    data={data.map((d) => ({ label: d.label, value: d.value as number }))}
    size="md"
    showValues
    showGrid
  />
);

export default BenchmarkGapsBar;
