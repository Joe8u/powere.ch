// Unified KPI checker: combines quick measurement and full inspect
// Usage:
//   node scripts/kpi_check.mjs [--mode quick|full|both] [--screenshot out.png] [URL]
// Defaults: mode=both, URL=http://127.0.0.1:4321/dashboard/

import puppeteer from 'puppeteer';

const args = process.argv.slice(2);
let mode = 'both';
let screenshotPath = process.env.KPI_SCREENSHOT || null;
let url = 'http://127.0.0.1:4321/dashboard/';
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === '--mode' && args[i + 1]) { mode = args[++i]; continue; }
  if (a === '--screenshot' && args[i + 1]) { screenshotPath = args[++i]; continue; }
  if (!a.startsWith('--')) url = a; // last positional wins
}

function formatPx(n) { return `${n.toFixed(1)}px`; }

async function run() {
  const browser = await puppeteer.launch({ headless: 'new' });
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-kpi-card]', { timeout: 5000 });

    const result = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('[data-kpi-card]'));
      const values = Array.from(document.querySelectorAll('.kpi-card .kpi-value'));
      // find common container
      let container = cards[0]?.parentElement || null;
      const containsAll = (node) => cards.every((c) => node && node.contains(c));
      while (container && !containsAll(container)) container = container.parentElement;
      if (!container) container = document.body;

      const cRect = container.getBoundingClientRect();
      const cStyle = getComputedStyle(container);

      // Quick metrics (per card)
      const quick = cards.map((card, i) => {
        const cr = card.getBoundingClientRect();
        const vv = card.querySelector('.kpi-value');
        const vr = vv?.getBoundingClientRect();
        return {
          card: i + 1,
          title: card.querySelector('.kpi-title')?.textContent?.trim() || '',
          width: cr.width,
          height: cr.height,
          bottomOffset: vr ? cr.bottom - vr.bottom : NaN,
          valueText: vv?.textContent?.trim() || '',
        };
      });

      // Full inspect
      const rootRem = parseFloat(getComputedStyle(document.documentElement).fontSize || '16') || 16;
      const valueMetrics = values.map((el, i) => {
        const r = el.getBoundingClientRect();
        const top = r.top - cRect.top;
        const bottom = cRect.bottom - r.bottom;
        const height = r.height;
        return {
          index: i + 1,
          top, bottom, height,
          topRem: top / rootRem,
          bottomRem: bottom / rootRem,
          heightRem: height / rootRem,
          text: el.textContent?.trim() || '',
        };
      });

      const cardBoxes = cards.map((el, i) => {
        const r = el.getBoundingClientRect();
        return { '#': i + 1, top: r.top - cRect.top, left: r.left - cRect.left, width: r.width, height: r.height };
      });

      const style = {
        display: cStyle.display,
        gridAutoRows: cStyle.gridAutoRows,
        gridTemplateColumns: cStyle.gridTemplateColumns,
        alignItems: cStyle.alignItems,
        alignContent: cStyle.alignContent,
        gap: cStyle.gap,
      };

      const maxTop = Math.max(...valueMetrics.map((m) => m.top));
      const maxBottom = Math.max(...valueMetrics.map((m) => m.bottom));
      const topSpread = Math.max(...valueMetrics.map((m) => m.top)) - Math.min(...valueMetrics.map((m) => m.top));
      const bottomSpread = Math.max(...valueMetrics.map((m) => m.bottom)) - Math.min(...valueMetrics.map((m) => m.bottom));

      return {
        container: { rect: { x: cRect.x, y: cRect.y, width: cRect.width, height: cRect.height }, style },
        quick,
        valueMetrics,
        cardBoxes,
        summary: { maxTop, maxBottom, topSpread, bottomSpread },
      };
    });

    console.log('KPI Unified Report for', url);

    if (mode === 'quick' || mode === 'both') {
      console.log('\nQuick metrics');
      console.table(result.quick.map((r) => ({ '#': r.card, title: r.title, width: formatPx(r.width), height: formatPx(r.height), bottomOffset: formatPx(r.bottomOffset), value: r.valueText })));
      console.log('\nJSON_QUICK:', JSON.stringify(result.quick));
    }

    if (mode === 'full' || mode === 'both') {
      console.log('\nContainer');
      console.table([{ width: formatPx(result.container.rect.width), height: formatPx(result.container.rect.height), gridAutoRows: result.container.style.gridAutoRows, alignItems: result.container.style.alignItems, alignContent: result.container.style.alignContent, gap: result.container.style.gap }]);

      console.log('\nValue metrics (relative to container)');
      console.table(result.valueMetrics.map((m) => ({ '#': m.index, top: formatPx(m.top), bottom: formatPx(m.bottom), height: formatPx(m.height), 'top (rem)': m.topRem.toFixed(3), 'bottom (rem)': m.bottomRem.toFixed(3), 'height (rem)': m.heightRem.toFixed(3), text: m.text })));

      console.log('\nCard boxes (relative to container)');
      console.table(result.cardBoxes.map((m) => ({ '#': m['#'], top: formatPx(m.top), left: formatPx(m.left), width: formatPx(m.width), height: formatPx(m.height) })));

      console.log('\nSummary');
      console.table([{ 'max top': formatPx(result.summary.maxTop), 'max bottom': formatPx(result.summary.maxBottom), 'top spread': formatPx(result.summary.topSpread), 'bottom spread': formatPx(result.summary.bottomSpread) }]);
      console.log('\nJSON_FULL:', JSON.stringify({ container: result.container, valueMetrics: result.valueMetrics, cardBoxes: result.cardBoxes, summary: result.summary }));
    }

    if (screenshotPath) {
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log('\nSaved screenshot to', screenshotPath);
    }
  } finally {
    await browser.close();
  }
}

run().catch((err) => { console.error(err); process.exit(1); });

