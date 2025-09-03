// Nur wenn du wirklich einen Chart willst:
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts';
import type { MfrrPoint } from '../types';
import { formatTs } from '../utils/format';

export default function MfrrChart({ rows }: { rows: MfrrPoint[] }) {
  const data = rows.map(r => ({
    ts: r.ts,                           // ISO beibehalten
    mw: Math.round(r.total_called_mw || 0),
  }));
  return (
    <div style={{ width: '100%', height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={data} syncId="time">
          <XAxis dataKey="ts" tickFormatter={(v: string) => formatTs(v)} minTickGap={24} />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="mw" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
