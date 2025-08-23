import { defineConfig } from 'astro/config'
import starlight from '@astrojs/starlight'
import react from '@astrojs/react'

export default defineConfig({
  site: 'https://www.powere.ch',
  integrations: [
    react(),
    starlight({
      title: 'powere.ch',
      description:
        'Virtuelle Kraftwerke (VPPs), dezentrale Flexibilität und ein KI-gestützter Guide – auf Basis eigener Forschung.',
      // logo: { src: './src/assets/logo.svg', replacesTitle: false },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/Joe8u/powere.ch' },
      ],
      sidebar: [
        { slug: 'executive-summary' },
        { link: '/methodik/', label: 'Methodik (6 Steps)' },
        {
          label: 'Mehr',
          items: [
            { link: '/guide/', label: 'KI-Guide (Beta)', badge: 'In Arbeit' },
            { link: '/kontakt/', label: 'Kontakt' },
          ],
        },
      ],
      // tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 3 },
    }),
  ],
})