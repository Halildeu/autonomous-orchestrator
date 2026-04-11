# @mfe/x-charts

Composable charting library for dashboards, reports, and inline data visualization. Internally wraps **Apache ECharts** with design-system tokens, responsive defaults, accessibility (WCAG AA), and interaction hooks.

> **Engine decision:** ECharts (Apache 2.0) is the primary rendering engine. AG Charts Community is used only for grid-linked embedded charts via `@mfe/x-data-grid`. See `decisions/topics/chart-viz-engine-selection.v1.json` in the orchestrator repo.

## Installation

```bash
pnpm add @mfe/x-charts
```

Peer dependencies:

```bash
pnpm add @mfe/design-system echarts
```

## Quick Start

```tsx
import { BarChart } from '@mfe/x-charts';

const data = [
  { month: 'Jan', revenue: 4000 },
  { month: 'Feb', revenue: 3000 },
  { month: 'Mar', revenue: 5000 },
  { month: 'Apr', revenue: 4500 },
];

export function RevenueChart() {
  return (
    <BarChart
      data={data}
      xAxis={{ dataKey: 'month' }}
      series={[{ dataKey: 'revenue', label: 'Revenue', color: 'primary' }]}
      height={300}
    />
  );
}
```

## Dashboard with KPIs

```tsx
import { KPICard, ChartDashboard, LineChart } from '@mfe/x-charts';

export function SalesDashboard() {
  return (
    <ChartDashboard columns={3}>
      <KPICard title="Total Revenue" value="$125K" trend={+12.5} />
      <KPICard title="Active Users" value="1,842" trend={-3.1} />
      <KPICard title="Conversion" value="4.2%" trend={+0.8} />
      <LineChart
        data={monthlyData}
        xAxis={{ dataKey: 'month' }}
        series={[{ dataKey: 'sales', label: 'Sales' }]}
        height={250}
      />
    </ChartDashboard>
  );
}
```

## Available Components

| Component | Description | Engine |
|-----------|-------------|--------|
| `BarChart` | Vertical / horizontal bar charts | ECharts |
| `LineChart` | Line and area charts | ECharts |
| `AreaChart` | Stacked / gradient area charts | ECharts |
| `PieChart` | Pie and donut charts | ECharts |
| `ScatterChart` | Scatter / bubble charts | ECharts |
| `SparklineChart` | Inline mini charts for tables and cards | ECharts |
| `FunnelChart` | Funnel / conversion charts | ECharts |
| `WaterfallChart` | Waterfall (bridge) charts | ECharts |
| `GaugeChart` | Gauge / speedometer charts | ECharts |
| `RadarChart` | Radar / spider charts | ECharts |
| `TreemapChart` | Treemap hierarchical charts | ECharts |
| `SunburstChart` | Sunburst hierarchical charts | ECharts |
| `SankeyChart` | Sankey flow diagrams | ECharts |
| `HeatmapChart` | Heatmap matrix charts | ECharts |
| `KPICard` | Key performance indicator card with trend | — |
| `ChartDashboard` | Grid layout for chart + KPI composition | — |

## Accessibility

All charts meet WCAG AA:
- Keyboard navigation (tab, arrow, enter)
- Data table fallback for screen readers
- Colorblind-safe palettes (4.5:1 contrast minimum)
- Decal patterns for non-color differentiation

## Hooks

| Hook | Description |
|------|-------------|
| `useChartInteractions` | Adds zoom, pan, and brush to any chart |
| `useRealTimeData` | Streams data updates into chart state |

## Bundle Size

Target: < 350KB gzip (tree-shaking enabled). CI gate enforces this limit.

## License

Private -- internal use only.
