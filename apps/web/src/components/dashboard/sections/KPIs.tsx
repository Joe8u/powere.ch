// apps/web/src/components/dashboard/sections/KPIs.tsx
import type { MfrrPoint, LastprofileRow, Agg } from '../types';
import { avg } from '../utils/math';
import { formatNumber } from '../utils/format';
import { KpiCard } from '../ui/KpiCard';

export function KPIs({ mfrr, lastp, lpSel, agg }: { mfrr: MfrrPoint[]; lastp?: LastprofileRow[] | null; lpSel?: string[]; agg: Agg }) {
  const price = avg(mfrr.map((x) => x.avg_price_eur_mwh ?? null));

  // Max. Preis (€/MWh)
  const maxPrice = (() => {
    const vals = mfrr.map((x) => x.avg_price_eur_mwh).filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
    return vals.length ? Math.max(...vals) : null;
  })();

  // Gesamtverbrauch der ausgewählten Lastprofile (MWh)
  const energyMWh = (() => {
    const rows = lastp ?? [];
    const keys = lpSel ?? [];
    if (!rows.length || !keys.length) return null;
    const stepHours = agg === 'raw' ? 0.25 : agg === 'hour' ? 1 : 24;
    let total = 0;
    for (const r of rows) {
      let mw = 0;
      for (const k of keys) {
        const v = r[k];
        if (typeof v === 'number' && Number.isFinite(v)) mw += v as number;
      }
      total += mw * stepHours;
    }
    return total;
  })();

  return (
    <section>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12, alignItems: 'stretch', alignContent: 'start', gridAutoRows: 'minmax(120px, auto)' }}>
        <KpiCard title="Durchschn. Preis" value={price != null ? `${formatNumber(price, 1)} €/MWh` : '–'} />
        <KpiCard title="Max. Preis" value={maxPrice != null ? `${formatNumber(maxPrice, 1)} €/MWh` : '–'} />
        <KpiCard title="Verbrauch (Summe)" value={energyMWh != null ? (energyMWh < 1 ? `${formatNumber(energyMWh * 1000, 0)} kWh` : `${formatNumber(energyMWh, 1)} MWh`) : '–'} />
      </div>
    </section>
  );
}
