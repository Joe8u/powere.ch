// Usage:
//  1) Start the dev server: npm --prefix apps/web run dev
//  2) In a second terminal:
//     npm --prefix apps/web run kpi:inspect -- [URL]
//     e.g. npm --prefix apps/web run kpi:inspect -- http://localhost:4321/dashboard/
//
// Optional env:
//  KPI_URL=... KPI_SCREENSHOT=out.png npm --prefix apps/web run kpi:inspect

import puppeteer from 'puppeteer';

const url = process.env.KPI_URL || process.argv[2] || 'http://localhost:4321/dashboard/';
const screenshotPath = process.env.KPI_SCREENSHOT || null;

function formatPx(n) { return `${n.toFixed(1)}px`; }

async function main() {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();

  page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: 'networkidle0' });

  // Wait for React islands to render
  await page.waitForSelector('.kpi-card .kpi-value', { timeout: 15000 });

  // Collect layout metrics inside the page context
  const result = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('.kpi-card'));
    const values = Array.from(document.querySelectorAll('.kpi-card .kpi-value'));
    if (!cards.length || !values.length) {
      return { error: 'No .kpi-card elements found' };
    }
    // Find the nearest common ancestor that contains all cards
    let container = cards[0].parentElement;
    const containsAll = (node) => cards.every((c) => node && node.contains(c));
    while (container && !containsAll(container)) container = container.parentElement;
    if (!container) container = document.body;

    const cRect = container.getBoundingClientRect();
    const cStyle = getComputedStyle(container);

    const rootRem = parseFloat(getComputedStyle(document.documentElement).fontSize || '16') || 16;
    const metrics = values.map((el, i) => {
      const r = el.getBoundingClientRect();
      const top = r.top - cRect.top;
      const bottom = cRect.bottom - r.bottom;
      const height = r.height;
      return {
        index: i + 1,
        top,
        bottom,
        height,
        topRem: top / rootRem,
        bottomRem: bottom / rootRem,
        heightRem: height / rootRem,
        text: el.textContent?.trim() || '',
      };
    });

    const titles = cards.map((card) => (
      card.querySelector('.kpi-title')?.textContent?.trim() || ''
    ));

    const cardMetrics = cards.map((el, i) => {
      const r = el.getBoundingClientRect();
      return {
        '#': i + 1,
        top: r.top - cRect.top,
        left: r.left - cRect.left,
        width: r.width,
        height: r.height,
      };
    });

    const style = {
      display: cStyle.display,
      gridAutoRows: cStyle.gridAutoRows,
      gridTemplateColumns: cStyle.gridTemplateColumns,
      alignItems: cStyle.alignItems,
      alignContent: cStyle.alignContent,
      gap: cStyle.gap,
      rowGap: cStyle.rowGap,
      columnGap: cStyle.columnGap,
    };

    const maxTop = Math.max(...metrics.map((m) => m.top));
    const maxBottom = Math.max(...metrics.map((m) => m.bottom));
    const topSpread = Math.max(...metrics.map((m) => m.top)) - Math.min(...metrics.map((m) => m.top));
    const bottomSpread = Math.max(...metrics.map((m) => m.bottom)) - Math.min(...metrics.map((m) => m.bottom));

    return {
      container: {
        rect: { x: cRect.x, y: cRect.y, width: cRect.width, height: cRect.height },
        style,
      },
      titles,
      metrics,
      cardMetrics,
      summary: { maxTop, maxBottom, topSpread, bottomSpread },
    };
  });

  if (result.error) {
    console.error('Error:', result.error);
    await browser.close();
    process.exit(1);
  }

  // Pretty print report
  const { container, titles, metrics, cardMetrics, summary } = result;
  console.log('KPI Layout Report for', url);
  console.log('\nContainer');
  console.table([{
    width: formatPx(container.rect.width),
    height: formatPx(container.rect.height),
    gridAutoRows: container.style.gridAutoRows,
    alignItems: container.style.alignItems,
    alignContent: container.style.alignContent,
    gap: container.style.gap,
  }]);

  console.log('\nCards');
  console.table(titles.map((t, i) => ({ '#': i + 1, title: t })));

  console.log('\nValue metrics (relative to container)');
  console.table(metrics.map((m) => ({ '#': m.index, top: formatPx(m.top), bottom: formatPx(m.bottom), height: formatPx(m.height), 'top (rem)': m.topRem.toFixed(3), 'bottom (rem)': m.bottomRem.toFixed(3), 'height (rem)': m.heightRem.toFixed(3), text: m.text })));

  console.log('\nCard boxes (relative to container)');
  console.table(cardMetrics.map((m) => ({ '#': m['#'], top: formatPx(m.top), left: formatPx(m.left), width: formatPx(m.width), height: formatPx(m.height) })));

  console.log('\nSummary');
  console.table([{ 'max top': formatPx(summary.maxTop), 'max bottom': formatPx(summary.maxBottom), 'top spread': formatPx(summary.topSpread), 'bottom spread': formatPx(summary.bottomSpread) }]);

  if (screenshotPath) {
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log('\nSaved screenshot to', screenshotPath);
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
