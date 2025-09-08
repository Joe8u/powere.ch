import React, { useEffect, useMemo, useRef, useState } from 'react';
import { KpiCard } from '../ui/KpiCard';
import DebugLayout from './DebugLayout';

type Metric = { top: number; bottom: number; height: number };
type CardBox = { idx: number; title: string; top: number; left: number; width: number; height: number; row: number };

export default function KpiInspector() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [titles, setTitles] = useState<string[]>([
    'Durchschn. Preis',
    'Max. Preis',
    'Verbrauch (Summe)',
  ]);
  const [values, setValues] = useState<string[]>(['149.9 €/MWh', '161.4 €/MWh', "6'108.0 MWh"]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [cards, setCards] = useState<CardBox[]>([]);
  const [autoMeasure, setAutoMeasure] = useState(true);

  const measure = () => {
    const root = containerRef.current;
    if (!root) return;
    const rect = root.getBoundingClientRect();

    // Measure values
    const nodes = root.querySelectorAll<HTMLElement>('.kpi-card .kpi-value');
    const ms: Metric[] = Array.from(nodes).map((el) => {
      const r = el.getBoundingClientRect();
      return { top: r.top - rect.top, bottom: rect.bottom - r.bottom, height: r.height };
    });
    setMetrics(ms);

    // Measure cards and infer rows
    const cardEls = Array.from(root.querySelectorAll<HTMLElement>('.kpi-card'));
    const raw = cardEls.map((el, i) => {
      const r = el.getBoundingClientRect();
      const t = el.querySelector('.kpi-title')?.textContent?.trim() || `Card ${i + 1}`;
      return { idx: i + 1, title: t, top: r.top - rect.top, left: r.left - rect.left, width: r.width, height: r.height };
    });
    const rowTops: number[] = [];
    const tol = 4; // px tolerance for grouping into rows
    const withRow: CardBox[] = raw
      .map((c) => {
        let row = rowTops.findIndex((t) => Math.abs(t - c.top) <= tol);
        if (row === -1) {
          rowTops.push(c.top);
          row = rowTops.length - 1;
        }
        return { ...c, row: row + 1 };
      })
      .sort((a, b) => a.idx - b.idx);
    setCards(withRow);
    // eslint-disable-next-line no-console
    console.debug('[KPI inspector]', { values: ms, cards: withRow });
  };

  useEffect(() => {
    measure();
    if (!autoMeasure) return;
    const onResize = () => measure();
    window.addEventListener('resize', onResize);
    const id = window.setInterval(measure, 300);
    return () => {
      window.removeEventListener('resize', onResize);
      window.clearInterval(id);
    };
  }, [autoMeasure, titles.join('|'), values.join('|')]);

  const maxTop = useMemo(() => (metrics.length ? Math.max(...metrics.map((m) => m.top)) : 0), [metrics]);
  const maxBottom = useMemo(() => (metrics.length ? Math.max(...metrics.map((m) => m.bottom)) : 0), [metrics]);
  const rowsUsed = useMemo(() => Array.from(new Set(cards.map((c) => c.row))).sort((a, b) => a - b), [cards]);
  const mismatchRow = useMemo(() => rowsUsed.length > 1, [rowsUsed]);

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <strong>Inspector Controls</strong>
        <label><input type="checkbox" checked={autoMeasure} onChange={(e) => setAutoMeasure(e.target.checked)} /> auto-measure</label>
        <button onClick={measure} style={{ padding: '4px 8px' }}>measure now</button>
      </div>

      <div style={{ display: 'grid', gap: 6 }}>
        {titles.map((t, i) => (
          <label key={i} style={{ display: 'flex', gap: 8 }}>
            Title {i + 1}
            <input style={{ flex: 1 }} value={t} onChange={(e) => setTitles((prev) => prev.map((x, idx) => (idx === i ? e.target.value : x)))} />
            Value {i + 1}
            <input style={{ flex: 1 }} value={values[i]} onChange={(e) => setValues((prev) => prev.map((x, idx) => (idx === i ? e.target.value : x)))} />
          </label>
        ))}
      </div>

      <div style={{ position: 'relative' }}>
        <div
          ref={containerRef}
          style={{
            position: 'relative',
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: 12,
            alignItems: 'stretch',
            alignContent: 'start',
            gridAutoRows: 'var(--kpi-card-h)',
            ['--kpi-card-h' as any]: 'clamp(9rem, 22vmin, 11rem)',
          }}
        >
          <KpiCard title={titles[0]} value={values[0]} />
          <KpiCard title={titles[1]} value={values[1]} />
          <KpiCard title={titles[2]} value={values[2]} />
          <DebugLayout container={containerRef.current} />
        </div>
        {cards.length > 0 && (
          <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
            {rowsUsed.map((r: number) => {
              const y = Math.min(...cards.filter((c) => c.row === r).map((c) => c.top));
              return <div key={r} style={{ position: 'absolute', left: 0, right: 0, top: y, height: 1, background: 'rgba(0,200,0,.45)' }} />
            })}
            {cards.map((c) => (
              <div key={c.idx} style={{ position: 'absolute', left: c.left + 4, top: c.top + 4, fontSize: 11, color: '#ccc', background: 'rgba(0,0,0,.35)', padding: '2px 4px', borderRadius: 4 }}>
                #{c.idx} r{c.row}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ fontSize: 13 }}>
        <div>
          <strong>Metrics</strong> (top from container, bottom to container bottom)
        </div>
        <ul>
          {metrics.map((m, i) => (
            <li key={i}>#{i + 1}: top {m.top.toFixed(1)} px · bottom {m.bottom.toFixed(1)} px · height {m.height.toFixed(1)} px</li>
          ))}
        </ul>
        <div>
          maxTop: {maxTop.toFixed(1)} px · maxBottom: {maxBottom.toFixed(1)} px
        </div>
        <div style={{ marginTop: 8 }}>
          <strong>Rows:</strong> {rowsUsed.join(', ') || '–'} {mismatchRow && (
            <span style={{ color: '#eab308' }}>· Achtung: Karten stehen nicht in einer Zeile</span>
          )}
          <div>
            {cards.map((c) => (
              <div key={c.idx}>#{c.idx} “{c.title}”: row {c.row}, top {c.top.toFixed(1)} px, height {c.height.toFixed(1)} px</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
