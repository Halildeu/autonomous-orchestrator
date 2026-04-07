/**
 * Storybook Stories: All Chart Types
 *
 * Visual catalog of every chart type supported by @mfe/x-charts.
 * Each story renders a REAL chart with sample data.
 *
 * @see contract P3-D DoD: "Storybook: all chart type stories"
 */
import React from 'react';
import { BarChart as BarChartComp } from '../BarChart';
import { LineChart as LineChartComp } from '../LineChart';
import { AreaChart as AreaChartComp } from '../AreaChart';
import { PieChart as PieChartComp } from '../PieChart';
import { ScatterChart as ScatterChartComp } from '../ScatterChart';
import { GaugeChart as GaugeChartComp } from '../GaugeChart';
import { RadarChart as RadarChartComp } from '../RadarChart';
import { TreemapChart as TreemapChartComp } from '../TreemapChart';
import { HeatmapChart as HeatmapChartComp } from '../HeatmapChart';
import { WaterfallChart as WaterfallChartComp } from '../WaterfallChart';
import { FunnelChart as FunnelChartComp } from '../FunnelChart';
import { SankeyChart as SankeyChartComp } from '../SankeyChart';
import { SunburstChart as SunburstChartComp } from '../SunburstChart';

/* ------------------------------------------------------------------ */
/*  Sample Data                                                        */
/* ------------------------------------------------------------------ */

const categories = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran'];
const values1 = [320, 332, 301, 334, 390, 330];
const values2 = [220, 182, 191, 234, 290, 330];

/* ------------------------------------------------------------------ */
/*  Stories                                                            */
/* ------------------------------------------------------------------ */

export default {
  title: 'Charts/All Chart Types',
  parameters: { layout: 'padded' },
};

export const BarChart = () => (
  <BarChartComp
    data={categories.map((c, i) => ({ label: c, value: values1[i] }))}
    title="Aylık Gelir"
    showValues
    showGrid
    size="lg"
  />
);

export const LineChart = () => (
  <LineChartComp
    series={[
      { name: 'Seri A', data: values1 },
      { name: 'Seri B', data: values2 },
    ]}
    labels={categories}
    title="Trend Analizi"
    showDots
    showLegend
    size="lg"
  />
);

export const AreaChart = () => (
  <AreaChartComp
    series={[
      { name: 'Gelir', data: values1 },
      { name: 'Gider', data: values2 },
    ]}
    labels={categories}
    title="Kümülatif Gösterim"
    stacked
    showLegend
    size="lg"
  />
);

export const PieChart = () => (
  <PieChartComp
    data={categories.slice(0, 5).map((c, i) => ({ label: c, value: values1[i] }))}
    title="Oran Dağılımı"
    showLabels
    showPercentage
    donut
    size="lg"
  />
);

export const ScatterChart = () => (
  <ScatterChartComp
    data={values1.map((v, i) => ({ x: v, y: values2[i], label: categories[i] }))}
    title="Korelasyon"
    xLabel="Seri A"
    yLabel="Seri B"
    size="lg"
  />
);

export const GaugeChart = () => (
  <GaugeChartComp
    value={72}
    min={0}
    max={100}
    title="Performans"
    thresholds={[
      { value: 30, color: '#ef4444' },
      { value: 70, color: '#f59e0b' },
      { value: 100, color: '#22c55e' },
    ]}
    size="lg"
  />
);

export const RadarChart = () => (
  <RadarChartComp
    indicators={[
      { name: 'Satış', max: 100 },
      { name: 'Pazarlama', max: 100 },
      { name: 'Teknoloji', max: 100 },
      { name: 'Destek', max: 100 },
      { name: 'Geliştirme', max: 100 },
    ]}
    series={[
      { name: 'Ekip A', values: [85, 70, 95, 60, 80] },
      { name: 'Ekip B', values: [65, 90, 70, 85, 55] },
    ]}
    title="Performans Profili"
    showLegend
    size="lg"
  />
);

export const TreemapChart = () => (
  <TreemapChartComp
    data={[
      {
        name: 'Satış', value: 100,
        children: [
          { name: 'Online', value: 60 },
          { name: 'Mağaza', value: 40 },
        ],
      },
      {
        name: 'Pazarlama', value: 80,
        children: [
          { name: 'Dijital', value: 50 },
          { name: 'Basılı', value: 30 },
        ],
      },
    ]}
    title="Departman Bütçesi"
    size="lg"
  />
);

export const HeatmapChart = () => (
  <HeatmapChartComp
    data={[
      [0, 0, 10], [0, 1, 22], [0, 2, 28],
      [1, 0, 35], [1, 1, 42], [1, 2, 18],
      [2, 0, 15], [2, 1, 30], [2, 2, 45],
      [3, 0, 50], [3, 1, 12], [3, 2, 33],
      [4, 0, 25], [4, 1, 38], [4, 2, 20],
    ]}
    xLabels={['Pzt', 'Sal', 'Çar', 'Per', 'Cum']}
    yLabels={['Sabah', 'Öğle', 'Akşam']}
    title="Yoğunluk Matrisi"
    showValues
    size="lg"
  />
);

export const WaterfallChart = () => (
  <WaterfallChartComp
    data={[
      { label: 'Başlangıç', value: 1000 },
      { label: 'Gelir', value: 300 },
      { label: 'Hizmet', value: 200 },
      { label: 'Gider', value: -150 },
      { label: 'Vergi', value: -100 },
      { label: 'Sonuç', value: 1250 },
    ]}
    title="Gelir Akışı"
    showValues
    size="lg"
  />
);

export const FunnelChart = () => (
  <FunnelChartComp
    data={[
      { label: 'Ziyaret', value: 5000 },
      { label: 'Kayıt', value: 3000 },
      { label: 'Deneme', value: 1500 },
      { label: 'Satın Alma', value: 500 },
    ]}
    title="Dönüşüm Hunisi"
    showConversion
    size="lg"
  />
);

export const SankeyChart = () => (
  <SankeyChartComp
    nodes={[
      { name: 'Kaynak A' },
      { name: 'Kaynak B' },
      { name: 'Hedef X' },
      { name: 'Hedef Y' },
    ]}
    links={[
      { source: 'Kaynak A', target: 'Hedef X', value: 30 },
      { source: 'Kaynak A', target: 'Hedef Y', value: 20 },
      { source: 'Kaynak B', target: 'Hedef X', value: 10 },
      { source: 'Kaynak B', target: 'Hedef Y', value: 40 },
    ]}
    title="Akış Diyagramı"
    size="lg"
  />
);

export const SunburstChart = () => (
  <SunburstChartComp
    data={[
      {
        name: 'Türkiye',
        children: [
          {
            name: 'İstanbul',
            children: [
              { name: 'Kadıköy', value: 50 },
              { name: 'Beşiktaş', value: 30 },
            ],
          },
          {
            name: 'Ankara',
            children: [
              { name: 'Çankaya', value: 40 },
              { name: 'Keçiören', value: 20 },
            ],
          },
        ],
      },
    ]}
    title="Hiyerarşik Dağılım"
    size="lg"
  />
);
