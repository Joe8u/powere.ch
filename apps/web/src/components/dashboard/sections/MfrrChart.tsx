import React from 'react';
import type { MfrrPoint } from '../types';
import { formatTs } from '../utils/format';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

export default function MfrrChart({ data }: { data: MfrrPoint[] | null }) {
  if (!data || data.length === 0) return null;

  return (
    <div style={{ width: '100%', height: 300, border: '1px solid #eee', borderRadius: 12, padding: 12 }}>
      <h3 style={{ margin: '0 0 8px 0' }}>mFRR – Verlauf</h3>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="ts"
            tickFormatter={(v: string) => formatTs(v).slice(5)} // kürzeres Label
            minTickGap={24}
          />
          <YAxis
            yAxisId="mw"
            label={{ value: 'MW', angle: -90, position: 'insideLeft' }}
            width={50}
          />
          <YAxis
            yAxisId="eur"
            orientation="right"
            label={{ value: '€/MWh', angle: -90, position: 'insideRight' }}
            width={60}
          />
          <Tooltip
            formatter={(val: number, name: string) =>
              name === 'avg_price_eur_mwh' ? [`${val.toFixed?.(1)} €/MWh`, 'Preis'] : [`${Math.round(val)} MW`, 'Abruf']
            }
            labelFormatter={(l: string) => formatTs(l)}
          />
          <Legend />
          <Line type="monotone" dataKey="total_called_mw" name="Abruf (MW)" yAxisId="mw" dot={false} />
          <Line type="monotone" dataKey="avg_price_eur_mwh" name="Preis (€/MWh)" yAxisId="eur" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}