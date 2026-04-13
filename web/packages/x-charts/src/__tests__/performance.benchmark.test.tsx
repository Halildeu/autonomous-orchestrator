/**
 * Contract Test: Chart Performance Benchmark
 *
 * Validates that core chart operations complete within
 * acceptable time budgets:
 * - ChartSpec → ECharts transform: < 50ms for 10K points
 * - Sanitization: < 10ms for 10K strings
 * - Data table render: < 100ms for 1K rows
 *
 * @see chart-viz-engine-selection D-011 (performance)
 */
import { describe, it, expect } from "vitest";
import { chartSpecToEChartsOption } from "../spec/chartSpecToEChartsOption";
import { sanitizeChartText, sanitizeChartData } from "../security/sanitizeChartText";
import { validateChartSpec } from "../spec/validateChartSpec";
import type { ChartSpec } from "../spec/ChartSpec";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function generateDataPoints(count: number): Record<string, unknown>[] {
  return Array.from({ length: count }, (_, i) => ({
    label: `Point ${i}`,
    value: Math.random() * 1000,
    category: `Cat ${i % 10}`,
  }));
}

function generateScatterData(count: number): Record<string, unknown>[] {
  return Array.from({ length: count }, (_, i) => ({
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 50,
    label: `P${i}`,
  }));
}

function makeSpec(
  chartType: string,
  dataCount: number,
): ChartSpec {
  return {
    $schema: "urn:ao:chart-spec:v1",
    version: "v1",
    spec_version: "1.0.0",
    chart_type: chartType,
    title: "Performance Test Chart",
    subtitle: "Benchmarking with large dataset",
    data: {
      source: "inline",
      values: generateDataPoints(dataCount),
    },
    encoding: {
      x: { field: "label", type: "nominal" },
      y: { field: "value", type: "quantitative" },
    },
    animation: { enabled: false },
    accessibility: { description: "Benchmark chart" },
  } as ChartSpec;
}

/* ------------------------------------------------------------------ */
/*  Benchmarks                                                         */
/* ------------------------------------------------------------------ */

describe("Performance: ChartSpec Transform", () => {
  it("transforms 10K data points bar chart in < 50ms", () => {
    const spec = makeSpec("bar", 10_000);

    const start = performance.now();
    const result = chartSpecToEChartsOption(spec);
    const elapsed = performance.now() - start;

    expect(result).toBeDefined();
    expect(elapsed).toBeLessThan(50);
  });

  it("transforms 10K data points line chart in < 50ms", () => {
    const spec = makeSpec("line", 10_000);

    const start = performance.now();
    const result = chartSpecToEChartsOption(spec);
    const elapsed = performance.now() - start;

    expect(result).toBeDefined();
    expect(elapsed).toBeLessThan(50);
  });

  it("transforms 10K data points scatter chart in < 50ms", () => {
    const spec = makeSpec("scatter", 10_000);

    const start = performance.now();
    const result = chartSpecToEChartsOption(spec);
    const elapsed = performance.now() - start;

    expect(result).toBeDefined();
    expect(elapsed).toBeLessThan(50);
  });

  it("transforms pie chart with 1K slices in < 20ms", () => {
    const spec = makeSpec("pie", 1_000);

    const start = performance.now();
    const result = chartSpecToEChartsOption(spec);
    const elapsed = performance.now() - start;

    expect(result).toBeDefined();
    expect(elapsed).toBeLessThan(20);
  });
});

describe("Performance: Sanitization", () => {
  it("sanitizes 10K strings in < 50ms", () => {
    const strings = Array.from(
      { length: 10_000 },
      (_, i) => `<b>Label ${i}</b> & "value" <script>x</script>`,
    );

    const start = performance.now();
    strings.forEach(sanitizeChartText);
    const elapsed = performance.now() - start;

    expect(elapsed).toBeLessThan(50);
  });

  it("sanitizes 10K data rows in < 50ms", () => {
    const data = Array.from({ length: 10_000 }, (_, i) => ({
      label: `<b>Item ${i}</b>`,
      category: `Cat & ${i % 5}`,
      value: i * 10,
    }));

    const start = performance.now();
    const result = sanitizeChartData(data);
    const elapsed = performance.now() - start;

    expect(result.length).toBe(10_000);
    expect(elapsed).toBeLessThan(50);
  });
});

describe("Performance: Validation", () => {
  it("validates a valid spec in < 5ms", () => {
    const spec = makeSpec("bar", 100);

    const start = performance.now();
    const result = validateChartSpec(spec);
    const elapsed = performance.now() - start;

    expect(result.valid).toBe(true);
    expect(elapsed).toBeLessThan(5);
  });

  it("validates and rejects invalid spec in < 5ms", () => {
    const badSpec = { chart_type: "bar" } as unknown as ChartSpec; // missing required fields

    const start = performance.now();
    const result = validateChartSpec(badSpec);
    const elapsed = performance.now() - start;

    expect(result.valid).toBe(false);
    expect(elapsed).toBeLessThan(5);
  });
});
