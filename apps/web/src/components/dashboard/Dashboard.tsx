import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';

type MfrrPoint = {
  ts: string;
  total_called_mw: number | null;
  avg_price_eur_mwh: number | null;
};

type SurveyRow = { respondent_id: string; age: number | null; gender: string | null };

// Nutzt PUBLIC_API_BASE, ansonsten stabile Fallback-URL (Prod).
// Für lokale Tests einfach in apps/web/.env.local setzen:
//   PUBLIC_API_BASE=http://127.0.0.1:9000
const API_BASE: string = (import.meta.env.PUBLIC_API_BASE as string | undefined) ?? 'https://api.powere.ch';
console.info('[Dashboard] API base =', API_BASE);

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    let body = '';
    try {
      body = await res.text();
    } catch {
      // ignore
    }
    throw new Error(`${url} → ${res.status} ${res.statusText}${body ? ` – ${body}` : ''}`);
  }
  return res.json() as Promise<T>;
}

export default function Dashboard() {
  const [mfrr, setMfrr] = useState<MfrrPoint[] | null>(null);
  const [survey, setSurvey] = useState<SurveyRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const [mfrrData, surveyData] = await Promise.all([
          fetchJson<MfrrPoint[]>(`${API_BASE}/warehouse/regelenergie/tertiary?agg=hour&limit=24`),
          fetchJson<SurveyRow[]>(`${API_BASE}/warehouse/survey/wide?columns=respondent_id,age,gender&limit=5`),
        ]);
        if (!cancelled) {
          setMfrr(mfrrData);
          setSurvey(surveyData);
        }
      } catch (e: any) {
        if (!cancelled) setErr(e?.message ?? 'Unbekannter Fehler');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <div>Lade Dashboard…</div>;
  if (err) return <div style={{ color: 'crimson' }}>Fehler: {err}</div>;

  const avgPrice = avg(mfrr?.map((x) => (x.avg_price_eur_mwh ?? 0)));
  const avgMw = avg(mfrr?.map((x) => (x.total_called_mw ?? 0)));

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
        <Kpi title="mFRR Punkte (24h)" value={mfrr?.length ?? 0} />
        <Kpi title="Durchschn. Preis (24h)" value={avgPrice != null ? `${avgPrice.toFixed(1)} €/MWh` : '–'} />
        <Kpi title="Durchschn. Abruf (24h)" value={avgMw != null ? `${avgMw.toFixed(0)} MW` : '–'} />
      </section>

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
              {(mfrr ?? []).map((r) => (
                <tr key={r.ts}>
                  <td style={td}>{r.ts.replace('T', ' ')}</td>
                  <td style={td}>{Math.round(r.total_called_mw ?? 0)}</td>
                  <td style={td}>{typeof r.avg_price_eur_mwh === 'number' ? r.avg_price_eur_mwh.toFixed(1) : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3>Survey (Beispiel: 5 Zeilen)</h3>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {(survey ?? []).map((r) => (
            <li key={r.respondent_id}>
              #{r.respondent_id} – {r.age ?? '–'} Jahre – {r.gender ?? '–'}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function avg(xs?: number[] | null): number | null {
  if (!xs || xs.length === 0) return null;
  const vals = xs.filter((n) => Number.isFinite(n));
  if (vals.length === 0) return null;
  const sum = vals.reduce((a, b) => a + b, 0);
  return sum / vals.length;
}

function Kpi({ title, value }: { title: string; value: ReactNode }) {
  return (
    <div style={{ padding: 16, border: '1px solid #eee', borderRadius: 12 }}>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

const th: CSSProperties = { textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid #eee' };
const td: CSSProperties = { padding: '6px 10px', borderBottom: '1px dotted #eee' };