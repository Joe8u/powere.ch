// apps/web/src/components/dashboard/sections/KPIs.tsx
import type { MfrrPoint } from '../types';
import { avg } from '../utils/math';
import { KpiCard } from '../ui/KpiCard';

export function KPIs({ mfrr }: { mfrr: MfrrPoint[] }) {
  const price = avg(mfrr.map((x) => x.avg_price_eur_mwh ?? null));
  const power = avg(mfrr.map((x) => x.total_called_mw ?? null));

  return (
    <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
      <KpiCard title="mFRR Punkte (24h)" value={mfrr.length} />
      <KpiCard title="Durchschn. Preis (24h)" value={price != null ? `${price.toFixed(1)} €/MWh` : '–'} />
      <KpiCard title="Durchschn. Abruf (24h)" value={power != null ? `${power.toFixed(0)} MW` : '–'} />
    </section>
  );
}