// Nur wenn du wirklich einen Chart willst:
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts';
import type { MfrrPoint } from '../types';

export default function MfrrChart({ rows }: { rows: MfrrPoint[] }) {
  const data = rows.map(r => ({
    ts: r.ts.slice(11, 16),  // HH:MM
    mw: Math.round(r.total_called_mw || 0),
  }));
  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <XAxis dataKey="ts" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="mw" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}