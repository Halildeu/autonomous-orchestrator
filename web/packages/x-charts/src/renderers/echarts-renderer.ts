/**
 * ECharts Renderer Lifecycle Manager
 *
 * Handles init, update, resize, dispose for ECharts instances.
 * Used by all chart components as the single rendering integration point.
 *
 * Key responsibilities:
 * - Instance creation with proper container binding
 * - Option merge with theme + sanitization
 * - Responsive resize (ResizeObserver)
 * - Memory-safe dispose (prevents leaks)
 * - Reduced motion respect
 * - Error boundary integration
 */

import { useRef, useEffect, useCallback, useState } from 'react';
import { echarts, registerECharts } from './echarts-imports';
import type { ECharts, EChartsOption } from './echarts-imports';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface EChartsRendererOptions {
  /** ECharts option object. */
  option: EChartsOption;
  /** Renderer type. @default 'canvas' */
  renderer?: 'canvas' | 'svg';
  /** Theme name or object (from DesignLabEChartsTheme). */
  theme?: string | object;
  /** Whether to merge or replace option on update. @default true */
  notMerge?: boolean;
  /** Whether to animate on update. @default true */
  lazyUpdate?: boolean;
  /** Callback when chart instance is ready. */
  onReady?: (instance: ECharts) => void;
  /** Callback on chart click event. */
  onClick?: (params: unknown) => void;
  /** Respect prefers-reduced-motion. @default true */
  respectReducedMotion?: boolean;
}

export interface EChartsRendererState {
  /** The ECharts container ref — attach to a div. */
  containerRef: React.RefObject<HTMLDivElement | null>;
  /** The ECharts instance (null until mounted). */
  instance: ECharts | null;
  /** Whether the chart has rendered at least once. */
  isReady: boolean;
  /** Force a resize recalculation. */
  resize: () => void;
}

/* ------------------------------------------------------------------ */
/*  Reduced motion detection                                           */
/* ------------------------------------------------------------------ */

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/* ------------------------------------------------------------------ */
/*  Hook: useEChartsRenderer                                           */
/* ------------------------------------------------------------------ */

export function useEChartsRenderer(options: EChartsRendererOptions): EChartsRendererState {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const instanceRef = useRef<ECharts | null>(null);
  const [isReady, setIsReady] = useState(false);

  const {
    option,
    renderer = 'canvas',
    theme,
    notMerge = false,
    lazyUpdate = true,
    onReady,
    onClick,
    respectReducedMotion = true,
  } = options;

  // Ensure ECharts modules are registered
  registerECharts();

  // Init / Dispose
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Init
    const instance = echarts.init(container, theme, {
      renderer,
      useDirtyRect: true, // Performance: only redraw changed areas
    });

    instanceRef.current = instance;
    setIsReady(true);
    onReady?.(instance);

    // Click handler
    if (onClick) {
      instance.on('click', onClick);
    }

    // ResizeObserver for responsive
    const observer = new ResizeObserver(() => {
      instance.resize({ animation: { duration: 200 } });
    });
    observer.observe(container);

    // Cleanup
    return () => {
      observer.disconnect();
      if (onClick) {
        instance.off('click', onClick);
      }
      instance.dispose();
      instanceRef.current = null;
      setIsReady(false);
    };
  }, [renderer, theme]);

  // Option update
  useEffect(() => {
    const instance = instanceRef.current;
    if (!instance || !option) return;

    let finalOption = option;

    // Disable animation if reduced motion preferred
    if (respectReducedMotion && prefersReducedMotion()) {
      finalOption = {
        ...finalOption,
        animation: false,
        animationDuration: 0,
        animationDurationUpdate: 0,
      };
    }

    instance.setOption(finalOption, { notMerge, lazyUpdate });
  }, [option, notMerge, lazyUpdate, respectReducedMotion]);

  const resize = useCallback(() => {
    instanceRef.current?.resize();
  }, []);

  return {
    containerRef,
    instance: instanceRef.current,
    isReady,
    resize,
  };
}
