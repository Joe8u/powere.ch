import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import type { LastprofileRow } from '../types';
import { formatTs } from '../utils/format';

export default function LastprofileChart({ rows, series }: { rows: LastprofileRow[]; series: string[] }) {
  // Recharts erwartet flache Keys je Serie; rows kommen bereits als { ts, <serie1>, <serie2>, ... }
  return (
    <div style={{ width: '100%', height: 260 }}>
      <ResponsiveContainer>
        <LineChart data={rows} syncId="time">
          <XAxis dataKey="ts" tickFormatter={(v: string) => formatTs(v)} minTickGap={24} />
          <YAxis />
          <Tooltip
            formatter={(val: any, name: string) => [
              typeof val === 'number' && Number.isFinite(val) ? `${Math.round(val)} MW` : '–',
              name,
            ]}
            labelFormatter={(l: string) => formatTs(l)}
          />
          <Legend />
          {series.map((s, idx) => (
            <Line key={s} type="monotone" dataKey={s} dot={false} stroke={COLORS[idx % COLORS.length]} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const COLORS = [
  '#2563eb', '#059669', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#e11d48'
];
