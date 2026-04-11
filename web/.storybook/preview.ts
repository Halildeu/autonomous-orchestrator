import type { Preview } from '@storybook/react';
import React from 'react';

const preview: Preview = {
  parameters: {
    controls: { expanded: true },
    layout: 'centered',

    // A11y — WCAG 2.1 AA
    a11y: {
      config: {
        rules: [
          { id: 'color-contrast', enabled: true },
          { id: 'label', enabled: true },
          { id: 'button-name', enabled: true },
        ],
      },
    },

    // Viewport presets
    viewport: {
      viewports: {
        mobile: { name: 'Mobile', styles: { width: '375px', height: '812px' } },
        tablet: { name: 'Tablet', styles: { width: '768px', height: '1024px' } },
        desktop: { name: 'Desktop', styles: { width: '1280px', height: '800px' } },
        wide: { name: 'Wide', styles: { width: '1920px', height: '1080px' } },
      },
    },

    // Backgrounds
    backgrounds: {
      default: 'light',
      values: [
        { name: 'light', value: '#ffffff' },
        { name: 'dark', value: '#0f172a' },
        { name: 'surface', value: '#f8fafc' },
        { name: 'canvas', value: '#f1f5f9' },
      ],
    },

    // Docs
    docs: {
      toc: true,
    },
  },

  globalTypes: {
    theme: {
      description: 'Theme',
      defaultValue: 'light',
      toolbar: {
        title: 'Theme',
        items: [
          { value: 'light', icon: 'sun', title: 'Light' },
          { value: 'dark', icon: 'moon', title: 'Dark' },
          { value: 'high-contrast', icon: 'accessibility', title: 'High Contrast' },
        ],
        dynamicTitle: true,
      },
    },
    density: {
      description: 'Density',
      defaultValue: 'comfortable',
      toolbar: {
        title: 'Density',
        items: [
          { value: 'comfortable', title: 'Comfortable' },
          { value: 'compact', title: 'Compact' },
        ],
        dynamicTitle: true,
      },
    },
    direction: {
      description: 'Text Direction',
      defaultValue: 'ltr',
      toolbar: {
        title: 'Direction',
        icon: 'globe',
        items: [
          { value: 'ltr', title: 'LTR' },
          { value: 'rtl', title: 'RTL' },
        ],
        dynamicTitle: true,
      },
    },
  },

  // Theme decorator
  decorators: [
    (Story: any, context: any) => {
      const theme = context.globals.theme || 'light';
      const density = context.globals.density || 'comfortable';
      const direction = context.globals.direction || 'ltr';

      // Set theme attributes on <html> for CSS to pick up
      if (typeof document !== 'undefined') {
        const root = document.documentElement;
        const isDark = theme === 'dark' || theme === 'high-contrast';
        root.setAttribute('data-mode', isDark ? 'dark' : 'light');
        root.setAttribute('data-appearance', theme);
        root.setAttribute('dir', direction);

        // Map to theme.css selector names
        const themeMap: Record<string, string> = {
          'light': 'serban-light',
          'dark': 'serban-dark',
          'high-contrast': 'serban-hc',
        };
        root.setAttribute('data-theme', themeMap[theme] || 'serban-light');
      }

      return React.createElement(
        'div',
        {
          'data-density': density,
          className: theme === 'dark' ? 'dark bg-slate-900 text-white p-4' : 'bg-white p-4',
          style: { minHeight: '100px' },
        },
        React.createElement(Story),
      );
    },
  ],
};

export default preview;
