import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://www.powere.ch',
  integrations: [
    starlight({
      title: 'powere.ch',
      description:
        'Virtuelle Kraftwerke (VPPs), dezentrale Flexibilität und ein KI-gestützter Guide – auf Basis eigener Forschung.',
      // Optionales Logo später:
      // logo: { src: './src/assets/logo.svg', replacesTitle: false },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/Joe8u/powere.ch' },
      ],
      // Schlanke Sidebar (mehr Seiten kannst du später ergänzen)
      sidebar: [
        { slug: 'executive-summary' },
        {
          label: 'Mehr',
          items: [
            { link: '/guide/', label: 'KI-Guide (Beta)', badge: 'In Arbeit' },
            { link: '/kontakt/', label: 'Kontakt' },
          ],
        },
      ],
      // Optional: Table-of-Contents global aus lassen/ändern:
      // tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 3 },
    }),
  ],
});