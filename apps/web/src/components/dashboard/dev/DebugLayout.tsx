import React, { useEffect, useMemo, useState } from 'react';

type Props = {
  container: React.RefObject<HTMLElement>;
};

type Metric = { top: number; bottom: number; height: number };

export function DebugLayout({ container }: Props) {
  const [metrics, setMetrics] = useState<Metric[]>([]);

  useEffect(() => {
    function measure() {
      const root = container.current;
      if (!root) return;
      const rect = root.getBoundingClientRect();
      const values = root.querySelectorAll<HTMLElement>('.kpi-card .kpi-value');
      const ms: Metric[] = Array.from(values).map((el) => {
        const r = el.getBoundingClientRect();
        return { top: r.top - rect.top, bottom: rect.bottom - r.bottom, height: r.height };
      });
      setMetrics(ms);
      // eslint-disable-next-line no-console
      console.debug('[KPI layout]', ms);
    }
    measure();
    const onResize = () => measure();
    window.addEventListener('resize', onResize);
    const id = window.setInterval(measure, 300); // simple watchdog while tweaking
    return () => { window.removeEventListener('resize', onResize); window.clearInterval(id); };
  }, [container]);

  const guideY = useMemo(() => (metrics.length ? Math.max(...metrics.map((m) => m.top)) : 0), [metrics]);

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
      <div style={{ position: 'absolute', left: 0, right: 0, top: guideY, height: 1, background: 'rgba(255,0,0,0.4)' }} />
      <div style={{ position: 'absolute', right: 6, top: 6, fontSize: 11, color: '#999', background: 'rgba(0,0,0,0.2)', padding: '4px 6px', borderRadius: 6 }}>
        {metrics.map((m, i) => (
          <div key={i}>#{i + 1}: top {m.top.toFixed(1)} px</div>
        ))}
      </div>
    </div>
  );
}

export default DebugLayout;
