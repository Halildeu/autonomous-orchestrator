/**
 * Inline ECharts Renderer for Design System Charts
 *
 * Lightweight hook that manages ECharts instance lifecycle.
 * Avoids circular dependency with @mfe/x-charts by importing
 * echarts directly (peerDep of design-system).
 */

import { useRef, useEffect, useState, useCallback } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, LineChart, PieChart, ScatterChart } from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  BarChart, LineChart, PieChart, ScatterChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent,
  CanvasRenderer,
]);

type EChartsInstance = ReturnType<typeof echarts.init>;

export interface InlineEChartsOptions {
  option: Record<string, unknown>;
  theme?: Record<string, unknown>;
  onClick?: (params: unknown) => void;
}

export function useInlineECharts(options: InlineEChartsOptions) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const instanceRef = useRef<EChartsInstance | null>(null);
  const [isReady, setIsReady] = useState(false);

  const { option, theme, onClick } = options;

  const sanitizeTapHighlightColor = useCallback((root: HTMLDivElement) => {
    const nodes = [root, ...Array.from(root.querySelectorAll<HTMLElement>('*'))];
    for (const node of nodes) {
      node.style.webkitTapHighlightColor = 'transparent';
    }
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const rect = el.getBoundingClientRect();
    const width = rect.width || el.clientWidth || 320;
    const height = rect.height || el.clientHeight || 200;
    const instance = echarts.init(el, theme, { renderer: 'canvas', width, height });
    instanceRef.current = instance;
    setIsReady(true);
    sanitizeTapHighlightColor(el);

    if (onClick) instance.on('click', onClick);

    const handleResize = () => {
      instance.resize();
      sanitizeTapHighlightColor(el);
    };
    let observer: ResizeObserver | null = null;

    if (typeof window !== 'undefined') {
      window.addEventListener('resize', handleResize);
    }

    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(handleResize);
      observer.observe(el);
    }

    return () => {
      observer?.disconnect();
      if (typeof window !== 'undefined') {
        window.removeEventListener('resize', handleResize);
      }
      if (onClick) instance.off('click', onClick);
      instance.dispose();
      instanceRef.current = null;
      setIsReady(false);
    };
  }, [onClick, sanitizeTapHighlightColor, theme]);

  useEffect(() => {
    if (!instanceRef.current || !option || Object.keys(option).length === 0) return;
    instanceRef.current.setOption(option, { notMerge: false });
    if (containerRef.current) {
      sanitizeTapHighlightColor(containerRef.current);
    }
  }, [option, sanitizeTapHighlightColor]);

  const resize = useCallback(() => instanceRef.current?.resize(), []);

  return { containerRef, isReady, resize };
}

/** Build a minimal light theme from CSS vars. */
export function buildLightTheme(): Record<string, unknown> {
  const get = (v: string, fb: string) => {
    if (typeof document === 'undefined') return fb;
    return getComputedStyle(document.documentElement).getPropertyValue(v).trim() || fb;
  };
  return {
    color: [get('--action-primary', '#3b82f6'), get('--state-success-text', '#22c55e'), get('--state-warning-text', '#f59e0b'), get('--state-error-text', '#ef4444'), get('--state-info-text', '#06b6d4'), get('--action-secondary', '#8b5cf6'), '#ec4899', '#14b8a6'],
    backgroundColor: 'transparent',
    textStyle: { fontFamily: get('--font-family-sans', 'Inter, system-ui, sans-serif'), color: get('--text-primary', '#1a1a2e') },
  };
}
