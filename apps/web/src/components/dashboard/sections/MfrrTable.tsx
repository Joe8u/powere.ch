// apps/web/src/components/dashboard/sections/MfrrTable.tsx
import type { MfrrPoint } from '../types';
import { formatTs } from '../utils/format';

const th: React.CSSProperties = { textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid #eee' };
const td: React.CSSProperties = { padding: '6px 10px', borderBottom: '1px dotted #eee' };

export function MfrrTable({ rows }: { rows: MfrrPoint[] }) {
  return (
    <section>
      <h3>mFRR (letzte 24h)</h3>
      <div style={{ fontSize: 14, maxHeight: 260, overflow: 'auto', border: '1px solid #eee', borderRadius: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={th}>Stunde</th>
              <th style={th}>MW</th>
              <th style={th}>€/MWh</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.ts}>
                <td style={td}>{formatTs(r.ts)}</td>
                <td style={td}>{Math.round(r.total_called_mw)}</td>
                <td style={td}>{r.avg_price_eur_mwh != null ? r.avg_price_eur_mwh.toFixed(1) : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}