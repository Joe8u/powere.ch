import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import react from '@astrojs/react';

export default defineConfig({
  site: 'https://www.powere.ch',
  integrations: [
    react(), // <-- gehört HIER hin (Top-Level)
    starlight({
      title: 'powere.ch',
      description:
        'Virtuelle Kraftwerke (VPPs), dezentrale Flexibilität und ein KI-gestützter Guide – auf Basis eigener Forschung.',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/Joe8u/powere.ch' },
      ],
      sidebar: [
        { slug: 'executive-summary' },
        { slug: 'dashboard', label: 'Dashboard (Beta)' },
        { link: '/methodik/', label: 'Methodik' },
        {
          label: 'Mehr',
          items: [
            { link: '/guide/', label: 'KI-Guide (Beta)', badge: 'In Arbeit' },
            { link: '/kontakt/', label: 'Kontakt' }, // ok, Link darf ins Leere zeigen
          ],
        },
      ],
      // Override RightSidebar so we can host the Dashboard ControlPanel via portal
      components: {
        RightSidebar: './src/components/starlight/RightSidebar.astro',
      },
      }),
  ],
});
