// Minimal KPI measurement script (PRE/POST), headless, domcontentloaded
// Usage: node scripts/kpi_measure.mjs [URL]
// Example: node scripts/kpi_measure.mjs http://127.0.0.1:4321/dashboard/

import puppeteer from 'puppeteer';

const url = process.argv[2] || 'http://127.0.0.1:4321/dashboard/';

function format(n) { return `${n.toFixed(1)}px`; }

async function measure() {
  const browser = await puppeteer.launch({ headless: 'new' });
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-kpi-card]', { timeout: 5000 });

    const data = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('[data-kpi-card]'));
      const rows = cards.slice(0, 3).map((card, idx) => {
        const value = card.querySelector('.kpi-value');
        const cr = card.getBoundingClientRect();
        const vr = value?.getBoundingClientRect();
        const bottomOffset = vr ? (cr.bottom - vr.bottom) : NaN;
        return {
          card: idx + 1,
          height: cr.height,
          bottomOffset,
          title: card.querySelector('.kpi-title')?.textContent?.trim() || '',
          valueText: value?.textContent?.trim() || '',
        };
      });
      return rows;
    });

    console.log('KPI PRE/POST metrics for', url);
    console.table(
      data.map((r) => ({
        card: r.card,
        title: r.title,
        height: format(r.height),
        bottomOffset: format(r.bottomOffset),
        value: r.valueText,
      }))
    );

    // Emit a compact JSON line for automation
    console.log('\nJSON:', JSON.stringify(data));
  } finally {
    await browser.close();
  }
}

measure().catch((err) => { console.error('ERR', err?.message || err); process.exit(1); });

