// Nur wenn du wirklich einen Chart willst:
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import type { MfrrPoint } from '../types';
import { formatTs } from '../utils/format';

export default function MfrrChart({ rows, showMw = true, showPrice = true }: { rows: MfrrPoint[]; showMw?: boolean; showPrice?: boolean }) {
  const data = rows.map(r => ({
    ts: r.ts,                                              // ISO beibehalten
    mw: Math.round(r.total_called_mw || 0),                // Leistung (MW)
    eur: r.avg_price_eur_mwh == null ? null : r.avg_price_eur_mwh, // Preis (€/MWh)
  }));

  // Dynamische Y-Achsenbereiche je sichtbarer Serie
  const nums = (xs: any[]) => xs.filter((v) => typeof v === 'number' && Number.isFinite(v)) as number[];
  const zeroDomain = (max: number) => {
    if (!Number.isFinite(max)) return undefined as unknown as [number, number];
    const upper = max === 0 ? 1 : max * 1.1; // 10% Luft nach oben, min. 1
    return [0, upper] as [number, number];
  };
  const mwVals = nums(data.map(d => d.mw));
  const eurVals = nums(data.map(d => d.eur));
  const mwDomain = showMw && mwVals.length ? zeroDomain(Math.max(...mwVals)) : undefined;
  const eurDomain = showPrice && eurVals.length ? zeroDomain(Math.max(...eurVals)) : undefined;
  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={data} syncId="time">
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="ts" tickFormatter={(v: string) => formatTs(v)} minTickGap={24} />
          {showMw && <YAxis yAxisId="mw" domain={mwDomain as any} />}
          {showPrice && <YAxis yAxisId="eur" orientation="right" domain={eurDomain as any} />}
          <Tooltip formatter={(val: any, name: string) => {
            if (name === 'eur') return [typeof val === 'number' ? `${val.toFixed(1)} €/MWh` : '–', 'Preis'];
            return [typeof val === 'number' ? `${Math.round(val)} MW` : '–', 'Abruf'];
          }} labelFormatter={(l: string) => formatTs(l)} />
          <Legend />
          {showMw && <Line type="monotone" dataKey="mw" yAxisId="mw" name="Abruf (MW)" stroke="#2563eb" dot={false} />}
          {showPrice && <Line type="monotone" dataKey="eur" yAxisId="eur" name="Preis (€/MWh)" stroke="#f59e0b" dot={false} />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
