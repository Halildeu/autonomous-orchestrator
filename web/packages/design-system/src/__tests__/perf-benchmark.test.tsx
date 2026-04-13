// @vitest-environment jsdom
/**
 * Performance Benchmarks
 *
 * Measures average render time for key components using @testing-library/react.
 * Each component is rendered `ITERATIONS` times; the top/bottom 10 % are trimmed
 * to reduce noise.  Thresholds are deliberately generous (5-10 ms) because JSDOM
 * is significantly slower than a real browser.
 */
import React from "react";
import { afterEach, describe, it, expect, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";

/* ------------------------------------------------------------------ */
/*  Mocks — AG Grid cannot render in jsdom                             */
/* ------------------------------------------------------------------ */
vi.mock("ag-grid-react", () => ({
  AgGridReact: (_props: Record<string, unknown>) => (
    <div data-testid="ag-grid-mock">AG Grid Mock</div>
  ),
}));
vi.mock("../advanced/data-grid/setup", () => ({
  AG_GRID_SETUP_COMPLETE: true,
}));

afterEach(cleanup);

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const ITERATIONS = 100;

function measureRenderTime(
  Component: React.ComponentType<any>,
  props: Record<string, any>,
  iterations = ITERATIONS,
): number {
  const times: number[] = [];

  for (let i = 0; i < iterations; i++) {
    const start = performance.now();
    const { unmount } = render(React.createElement(Component, { key: i, ...props }));
    const end = performance.now();
    times.push(end - start);
    unmount();
  }

  // Remove top/bottom 10 % outliers
  times.sort((a, b) => a - b);
  const lo = Math.floor(times.length * 0.1);
  const hi = Math.floor(times.length * 0.9);
  const trimmed = times.slice(lo, hi);
  return trimmed.reduce((sum, t) => sum + t, 0) / trimmed.length;
}

/* ------------------------------------------------------------------ */
/*  Benchmarks                                                         */
/* ------------------------------------------------------------------ */

describe("Performance Benchmarks", () => {
  it("Button renders under 5ms average", async () => {
    const { Button } = await import("../primitives/button");
    const avg = measureRenderTime(Button, { children: "Click me" });
    console.log(`Button: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(5);
  });

  it("Input renders under 5ms average", async () => {
    const { Input } = await import("../primitives/input");
    const avg = measureRenderTime(Input, { placeholder: "Type..." });
    console.log(`Input: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(5);
  });

  it("Select renders under 5ms average", async () => {
    const { Select } = await import("../primitives/select");
    const options = [
      { value: "a", label: "Alpha" },
      { value: "b", label: "Beta" },
      { value: "c", label: "Gamma" },
    ];
    const avg = measureRenderTime(Select, { options, placeholder: "Choose..." });
    console.log(`Select: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(5);
  });

  it("Checkbox renders under 5ms average", async () => {
    const { Checkbox } = await import("../primitives/checkbox");
    const avg = measureRenderTime(Checkbox, { label: "Accept terms" });
    console.log(`Checkbox: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(5);
  });

  it("Switch renders under 5ms average", async () => {
    const { Switch } = await import("../primitives/switch");
    const avg = measureRenderTime(Switch, { label: "Enable feature" });
    console.log(`Switch: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(5);
  });

  it("Tabs renders under 10ms average", async () => {
    const { Tabs } = await import("../components/tabs");
    const items = [
      { key: "tab1", label: "Tab 1", content: React.createElement("div", null, "Content 1") },
      { key: "tab2", label: "Tab 2", content: React.createElement("div", null, "Content 2") },
      { key: "tab3", label: "Tab 3", content: React.createElement("div", null, "Content 3") },
    ];
    const avg = measureRenderTime(Tabs, { items });
    console.log(`Tabs: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(10);
  });

  it("Dialog renders under 10ms average", async () => {
    const { Dialog } = await import("../primitives/dialog");
    const noop = () => {};
    const avg = measureRenderTime(Dialog, {
      open: false,
      onClose: noop,
      title: "Test Dialog",
      children: React.createElement("p", null, "Dialog body"),
    });
    console.log(`Dialog: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(10);
  });

  it("Accordion renders under 10ms average", async () => {
    const { Accordion } = await import("../components/accordion");
    const items = [
      { value: "item1", title: "Section 1", content: React.createElement("p", null, "Content 1") },
      { value: "item2", title: "Section 2", content: React.createElement("p", null, "Content 2") },
      { value: "item3", title: "Section 3", content: React.createElement("p", null, "Content 3") },
    ];
    const avg = measureRenderTime(Accordion, { items });
    console.log(`Accordion: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(10);
  });

  it("ToastProvider renders under 5ms average", async () => {
    const { ToastProvider } = await import("../components/toast");
    const avg = measureRenderTime(ToastProvider, {
      children: React.createElement("div", null, "App"),
    });
    console.log(`ToastProvider: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(5);
  });

  it("Tooltip renders under 5ms average", async () => {
    const { Tooltip } = await import("../primitives/tooltip");
    const avg = measureRenderTime(Tooltip, {
      content: "Helpful tip",
      children: React.createElement("span", null, "Hover me"),
    });
    console.log(`Tooltip: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(5);
  });

  it("DataGrid renders under 15ms average", async () => {
    const { GridShell } = await import("../advanced/data-grid");
    const columnDefs = [
      { field: "name", headerName: "Name" },
      { field: "value", headerName: "Value" },
    ];
    const rowData = [
      { name: "Row 1", value: 100 },
      { name: "Row 2", value: 200 },
    ];
    const avg = measureRenderTime(GridShell, { columnDefs, rowData });
    console.log(`DataGrid: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(15);
  });

  it("Combobox renders under 10ms average", async () => {
    const { Combobox } = await import("../components/combobox");
    const options = [
      { value: "apple", label: "Apple" },
      { value: "banana", label: "Banana" },
      { value: "cherry", label: "Cherry" },
    ];
    const avg = measureRenderTime(Combobox, {
      options,
      label: "Fruit",
      placeholder: "Select a fruit...",
    });
    console.log(`Combobox: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(10);
  });

  it("DatePicker renders under 15ms average", async () => {
    const { DatePicker } = await import("../components/date-picker");
    const avg = measureRenderTime(DatePicker, {
      label: "Start date",
      placeholder: "YYYY-MM-DD",
    });
    console.log(`DatePicker: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(15);
  });

  it("Slider renders under 10ms average", async () => {
    const { Slider } = await import("../components/slider");
    const avg = measureRenderTime(Slider, {
      label: "Volume",
      min: 0,
      max: 100,
      defaultValue: 50,
    });
    console.log(`Slider: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(10);
  });

  it("Pagination renders under 10ms average", async () => {
    const { Pagination } = await import("../components/pagination");
    const avg = measureRenderTime(Pagination, {
      total: 200,
      current: 1,
      pageSize: 10,
    });
    console.log(`Pagination: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(10);
  });

  it("SearchInput renders under 5ms average", async () => {
    const { SearchInput } = await import("../components/search-input");
    const avg = measureRenderTime(SearchInput, {
      placeholder: "Search...",
    });
    console.log(`SearchInput: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(5);
  });

  /* ------------------------------------------------------------------ */
  /*  Heavy components                                                    */
  /* ------------------------------------------------------------------ */

  it("Calendar renders under 15ms average", async () => {
    const { Calendar } = await import("../components/calendar");
    const avg = measureRenderTime(Calendar, {
      defaultMonth: new Date(2026, 0, 1),
      mode: "single",
    });
    console.log(`Calendar: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(15);
  });

  it("ColorPicker renders under 15ms average", async () => {
    const { ColorPicker } = await import("../components/color-picker");
    const avg = measureRenderTime(ColorPicker, {
      defaultValue: "var(--action-primary)",
      label: "Brand color",
    });
    console.log(`ColorPicker: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(15);
  });

  it("Carousel renders under 10ms average", async () => {
    const { Carousel } = await import("../components/carousel");
    const items = [
      { key: "s1", content: React.createElement("div", null, "Slide 1") },
      { key: "s2", content: React.createElement("div", null, "Slide 2") },
      { key: "s3", content: React.createElement("div", null, "Slide 3") },
      { key: "s4", content: React.createElement("div", null, "Slide 4") },
    ];
    const avg = measureRenderTime(Carousel, { items });
    console.log(`Carousel: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(10);
  });

  it("CommandPalette renders under 5ms average", async () => {
    const { CommandPalette } = await import("../components/command-palette");
    const items = [
      { id: "cmd1", title: "Go to Dashboard", group: "Navigation", shortcut: "G D" },
      { id: "cmd2", title: "Create Project", group: "Actions", shortcut: "C P" },
      { id: "cmd3", title: "Search Files", group: "Navigation", shortcut: "S F" },
      { id: "cmd4", title: "Toggle Theme", group: "Settings" },
      { id: "cmd5", title: "Open Settings", group: "Settings", shortcut: "," },
    ];
    const noop = () => {};
    const avg = measureRenderTime(CommandPalette, {
      open: false,
      items,
      onClose: noop,
    });
    console.log(`CommandPalette: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(5);
  });

  it("TreeTable renders under 10ms average", async () => {
    const { TreeTable } = await import("../components/tree-table");
    const columns = [
      { key: "size", label: "Size", accessor: "size" as const },
      { key: "type", label: "Type", accessor: "type" as const },
    ];
    const nodes = [
      {
        key: "src",
        label: "src",
        data: { size: "4 KB", type: "folder" },
        children: [
          { key: "index", label: "index.ts", data: { size: "1 KB", type: "file" } },
          { key: "app", label: "App.tsx", data: { size: "2 KB", type: "file" } },
        ],
      },
      {
        key: "pkg",
        label: "package.json",
        data: { size: "1 KB", type: "file" },
      },
    ];
    const avg = measureRenderTime(TreeTable, { nodes, columns });
    console.log(`TreeTable: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(10);
  });

  it("Transfer renders under 50ms average", async () => {
    const { Transfer } = await import("../components/transfer");
    const dataSource = Array.from({ length: 20 }, (_, i) => ({
      key: `item-${i}`,
      label: `Item ${i + 1}`,
      description: `Description for item ${i + 1}`,
    }));
    const avg = measureRenderTime(Transfer, {
      dataSource,
      targetKeys: ["item-2", "item-5", "item-8"],
      titles: ["Available", "Selected"] as [string, string],
    });
    console.log(`Transfer: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(50);
  });

  it("SmartDashboard renders under 15ms average", async () => {
    const { SmartDashboard } = await import("../components/smart-dashboard");
    const widgets = [
      { key: "w1", title: "Revenue", type: "kpi" as const, value: "$12,340", tone: "success" as const },
      { key: "w2", title: "Active Users", type: "kpi" as const, value: 1523, tone: "info" as const },
      { key: "w3", title: "Error Rate", type: "kpi" as const, value: "0.4%", tone: "warning" as const },
      { key: "w4", title: "Uptime", type: "kpi" as const, value: "99.9%", tone: "success" as const },
    ];
    const avg = measureRenderTime(SmartDashboard, {
      widgets,
      title: "System Overview",
      columns: 2,
    });
    console.log(`SmartDashboard: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(15);
  });

  it("Timeline renders under 10ms average", async () => {
    const { Timeline } = await import("../components/timeline");
    const items = [
      { key: "t1", children: React.createElement("span", null, "Project created"), color: "info" as const, label: "Jan 2026" },
      { key: "t2", children: React.createElement("span", null, "First release"), color: "success" as const, label: "Feb 2026" },
      { key: "t3", children: React.createElement("span", null, "Major update"), color: "warning" as const, label: "Mar 2026" },
      { key: "t4", children: React.createElement("span", null, "Milestone reached"), color: "success" as const, label: "Apr 2026" },
    ];
    const avg = measureRenderTime(Timeline, { items });
    console.log(`Timeline: ${avg.toFixed(2)}ms avg`);
    expect(avg).toBeLessThan(10);
  });
});
