// Nur wenn du wirklich einen Chart willst:
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import type { MfrrPoint } from '../types';
import { formatTs } from '../utils/format';

export default function MfrrChart({ rows }: { rows: MfrrPoint[] }) {
  const data = rows.map(r => ({
    ts: r.ts,                                              // ISO beibehalten
    mw: Math.round(r.total_called_mw || 0),                // Leistung (MW)
    eur: r.avg_price_eur_mwh == null ? null : r.avg_price_eur_mwh, // Preis (€/MWh)
  }));
  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={data} syncId="time">
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="ts" tickFormatter={(v: string) => formatTs(v)} minTickGap={24} />
          <YAxis yAxisId="mw" />
          <YAxis yAxisId="eur" orientation="right" />
          <Tooltip formatter={(val: any, name: string) => {
            if (name === 'eur') return [typeof val === 'number' ? `${val.toFixed(1)} €/MWh` : '–', 'Preis'];
            return [typeof val === 'number' ? `${Math.round(val)} MW` : '–', 'Abruf'];
          }} labelFormatter={(l: string) => formatTs(l)} />
          <Legend />
          <Line type="monotone" dataKey="mw" yAxisId="mw" name="Abruf (MW)" stroke="#2563eb" dot={false} />
          <Line type="monotone" dataKey="eur" yAxisId="eur" name="Preis (€/MWh)" stroke="#f59e0b" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
