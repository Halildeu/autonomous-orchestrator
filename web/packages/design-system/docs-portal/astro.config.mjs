import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  integrations: [
    starlight({
      title: '@mfe/design-system',
      description: 'Enterprise-grade AI-native React design system',
      defaultLocale: 'en',
      locales: {
        en: { label: 'English' },
        tr: { label: 'Türkçe' },
      },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/mfe/design-system' },
      ],
      sidebar: [
        {
          label: 'Getting Started',
          items: [
            { label: 'Installation', link: '/getting-started/installation/' },
            { label: 'Quick Start', link: '/getting-started/quick-start/' },
            { label: 'Theming', link: '/getting-started/theming/' },
          ],
        },
        {
          label: 'Components',
          autogenerate: { directory: 'components' },
        },
        {
          label: 'Patterns',
          autogenerate: { directory: 'patterns' },
        },
        {
          label: 'Tokens',
          items: [
            { label: 'Color', link: '/tokens/color/' },
            { label: 'Spacing', link: '/tokens/spacing/' },
            { label: 'Typography', link: '/tokens/typography/' },
            { label: 'Motion', link: '/tokens/motion/' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'Form Validation', link: '/guides/form-validation/' },
            { label: 'Accessibility', link: '/guides/accessibility/' },
            { label: 'RTL Support', link: '/guides/rtl/' },
            { label: 'Animation', link: '/guides/animation/' },
            { label: 'AG Grid', link: '/guides/ag-grid/' },
          ],
        },
        {
          label: 'Blocks',
          autogenerate: { directory: 'blocks' },
        },
        {
          label: 'Migration',
          items: [
            { label: 'v1 to v2', link: '/migration/v1-to-v2/' },
          ],
        },
        {
          label: 'API Reference',
          autogenerate: { directory: 'api' },
        },
      ],
      editLink: {
        baseUrl: 'https://github.com/mfe/design-system/edit/main/docs-portal/',
      },
      customCss: ['./src/styles/custom.css'],
    }),
  ],
});
