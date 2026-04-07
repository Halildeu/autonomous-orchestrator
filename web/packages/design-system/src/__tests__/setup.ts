/**
 * Vitest global setup
 *  - jest-dom matchers (toBeInTheDocument, toHaveAttribute, etc.)
 *  - suppress runtime noise that is not actionable
 */
import * as matchers from '@testing-library/jest-dom/matchers';
import { expect } from 'vitest';

expect.extend(matchers);

// ---------------------------------------------------------------------------
// Suppress known non-actionable warnings in test environment
// ---------------------------------------------------------------------------
const SUPPRESSED_PATTERNS = [
  'AG Grid',
  'ag-grid',
  'AG Charts',
  'ag-charts',
  'deprecated',
  'selectSize',
  'onValueChange',
  'Unknown event handler',
  'act(...)',
  'act(() =>',
  'ReactDOM.render',
  'Vite CJS',
  'Path2D',
  'setTransform',
  'content layer',
  'tailwind',
  'canvas',
  'getContext',
  'not implemented',
  'Not implemented',
  'Error: Not implemented',
  'Could not parse CSS',
  'React does not recognize',
  'contract error',
  'a11y test',
  'chunk failed',
  'lazy import failed',
  'Test error',
  'callback test',
  'reset test',
  'render fn test',
  'useToast must be used within <ToastProvider>',
  'useTheme must be used within <ThemeProvider>',
  'useFormContext must be used within a <FormProvider>',
];

const toSearchableText = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (value instanceof Error) {
    return [value.name, value.message, value.stack].filter(Boolean).join(' ');
  }
  if (typeof value === 'object' && value !== null) {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value ?? '');
};

const containsSuppressedPattern = (value: unknown): boolean => {
  const text = toSearchableText(value);
  return SUPPRESSED_PATTERNS.some((pattern) => text.includes(pattern));
};

const isSuppressed = (args: unknown[]): boolean => {
  return args.some((arg) => containsSuppressedPattern(arg));
};

const origWarn = console.warn;
const origError = console.error;
const origInfo = console.info;
const origLog = console.log;

console.warn = (...args: unknown[]) => {
  if (isSuppressed(args)) return;
  origWarn.apply(console, args);
};
console.error = (...args: unknown[]) => {
  if (isSuppressed(args)) return;
  origError.apply(console, args);
};
console.info = (...args: unknown[]) => {
  if (isSuppressed(args)) return;
  origInfo.apply(console, args);
};
console.log = (...args: unknown[]) => {
  if (isSuppressed(args)) return;
  origLog.apply(console, args);
};

const createCanvasContextStub = () => ({
  fillRect: () => undefined,
  clearRect: () => undefined,
  getImageData: () => ({ data: [] }),
  putImageData: () => undefined,
  createImageData: () => [],
  setTransform: () => undefined,
  drawImage: () => undefined,
  save: () => undefined,
  restore: () => undefined,
  fillText: () => undefined,
  strokeText: () => undefined,
  beginPath: () => undefined,
  moveTo: () => undefined,
  lineTo: () => undefined,
  closePath: () => undefined,
  stroke: () => undefined,
  translate: () => undefined,
  scale: () => undefined,
  rotate: () => undefined,
  arc: () => undefined,
  fill: () => undefined,
  measureText: () => ({ width: 0 }),
  transform: () => undefined,
  rect: () => undefined,
  clip: () => undefined,
});

const OUTPUT_SUPPRESSED_PATTERNS = [
  'Could not parse CSS stylesheet',
  'ag-charts-community/dist/package/main.esm.mjs',
  'Error: Uncaught [Error: callback test]',
  'Error: Uncaught [Error: reset test]',
  'Error: Uncaught [Error: render fn test]',
  'The above error occurred in the <ThrowingChild> component',
];

const shouldSuppressOutputChunk = (chunk: unknown): boolean => {
  const text = toSearchableText(chunk);
  return OUTPUT_SUPPRESSED_PATTERNS.some((pattern) => text.includes(pattern));
};

// JSDOM stubs for APIs not implemented in jsdom

// ResizeObserver — used by useInlineECharts, ECharts renderers, and chart containers
if (typeof globalThis !== 'undefined' && !globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class ResizeObserver {
    private cb: ResizeObserverCallback;
    constructor(cb: ResizeObserverCallback) { this.cb = cb; }
    observe() { /* noop in test */ }
    unobserve() { /* noop in test */ }
    disconnect() { /* noop in test */ }
  };
}

if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => undefined;
}
if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
}

if (typeof HTMLCanvasElement !== 'undefined') {
  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    configurable: true,
    value: () => createCanvasContextStub(),
  });

  Object.defineProperty(HTMLCanvasElement.prototype, 'toDataURL', {
    configurable: true,
    value: () => 'data:image/png;base64,',
  });
}

if (typeof window !== 'undefined') {
  window.addEventListener('error', (event) => {
    if (containsSuppressedPattern(event.error) || containsSuppressedPattern(event.message)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  });

  window.addEventListener('unhandledrejection', (event) => {
    if (containsSuppressedPattern(event.reason)) {
      event.preventDefault();
    }
  });
}

if (typeof process !== 'undefined') {
  const origStderrWrite = process.stderr.write.bind(process.stderr);
  process.stderr.write = (((chunk: string | Uint8Array, ...rest: unknown[]) => {
    if (shouldSuppressOutputChunk(chunk)) {
      const callback = rest.find((value) => typeof value === 'function');
      if (typeof callback === 'function') {
        callback();
      }
      return true;
    }
    return origStderrWrite(chunk, ...(rest as []));
  }) as typeof process.stderr.write);
}
