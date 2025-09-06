import React, { useEffect, useMemo, useRef, useState } from 'react';
import { KpiCard } from '../ui/KpiCard';
import DebugLayout from './DebugLayout';

type Metric = { top: number; bottom: number; height: number };

export default function KpiInspector() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [titles, setTitles] = useState<string[]>([
    'Durchschn. Preis',
    'Max. Preis',
    'Verbrauch (Summe)',
  ]);
  const [values, setValues] = useState<string[]>(['149.9 €/MWh', '161.4 €/MWh', "6'108.0 MWh"]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [autoMeasure, setAutoMeasure] = useState(true);

  const measure = () => {
    const root = containerRef.current;
    if (!root) return;
    const rect = root.getBoundingClientRect();
    const nodes = root.querySelectorAll<HTMLElement>('.kpi-card .kpi-value');
    const ms: Metric[] = Array.from(nodes).map((el) => {
      const r = el.getBoundingClientRect();
      return { top: r.top - rect.top, bottom: rect.bottom - r.bottom, height: r.height };
    });
    setMetrics(ms);
    // eslint-disable-next-line no-console
    console.debug('[KPI inspector]', ms);
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
            <input style={{ flex: 1 }} value={t} onChange={(e) => setTitles((prev) => prev.map((x, idx) => idx === i ? e.target.value : x))} />
            Value {i + 1}
            <input style={{ flex: 1 }} value={values[i]} onChange={(e) => setValues((prev) => prev.map((x, idx) => idx === i ? e.target.value : x))} />
          </label>
        ))}
      </div>
      <div style={{ position: 'relative' }}>
        <div
          ref={containerRef}
          style={{
            position: 'relative',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))',
            gap: 12,
            alignItems: 'stretch',
            alignContent: 'start',
            gridAutoRows: 'minmax(120px, auto)'
          }}
        >
          <KpiCard title={titles[0]} value={values[0]} />
          <KpiCard title={titles[1]} value={values[1]} />
          <KpiCard title={titles[2]} value={values[2]} />
          <DebugLayout container={containerRef.current} />
        </div>
      </div>
      <div style={{ fontSize: 13 }}>
        <div><strong>Metrics</strong> (top from container, bottom to container bottom)</div>
        <ul>
          {metrics.map((m, i) => (
            <li key={i}>#{i + 1}: top {m.top.toFixed(1)} px · bottom {m.bottom.toFixed(1)} px · height {m.height.toFixed(1)} px</li>
          ))}
        </ul>
        <div>maxTop: {maxTop.toFixed(1)} px · maxBottom: {maxBottom.toFixed(1)} px</div>
      </div>
    </div>
  );
}

