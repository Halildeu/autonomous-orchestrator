import React from 'react';
import { BarChart } from '@mfe/x-charts';
import type { ChartDataRow } from '../types';

type Props = { data: ChartDataRow[] };

const ProviderCapabilitiesBar: React.FC<Props> = ({ data }) => (
  <BarChart
    data={data.map((d) => ({ label: d.label, value: d.value as number }))}
    orientation="horizontal"
    size="md"
    showValues
    showGrid
  />
);

export default ProviderCapabilitiesBar;
