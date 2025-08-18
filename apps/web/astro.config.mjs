// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import react from '@astrojs/react';
import mdx from '@astrojs/mdx';

export default defineConfig({
  integrations: [
    starlight({
      title: 'powere.ch',
      customCss: ['./src/styles/theme.css'],
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/Joe8u/powere.ch' },
      ],
      sidebar: [
        {
          label: 'Overview',
          items: [
            { label: 'Start', slug: 'index' },
            { label: 'Executive Summary', slug: 'executive-summary' },
          ],
        },
        {
          label: 'Guides',
          items: [{ label: 'Example Guide', slug: 'guides/example' }],
        },
        {
          label: 'About',
          items: [{ label: 'Über powere.ch', slug: 'about' }],
        },
        {
          label: 'Reference',
          autogenerate: { directory: 'reference' },
        },
      ],
    }),
    react(),
    mdx(),
  ],
});