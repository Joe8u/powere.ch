import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';

import { useMfrr } from './hooks/useMfrr';
import { useSurvey } from './hooks/useSurvey';
import { KPIs } from './sections/KPIs';
import { MfrrTable } from './sections/MfrrTable';
import { SurveyList } from './sections/SurveyList';
import { ErrorBanner } from './ui/ErrorBanner';
import { Loading } from './ui/Loading';

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
  const { data: mfrr, loading: l1, error: e1 } = useMfrr({ agg: 'hour', limit: 24 });
  const { data: survey, loading: l2, error: e2 } = useSurvey({ limit: 5 });

  if (l1 || l2) return <Loading>Lade Dashboard…</Loading>;

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {(e1 || e2) && <ErrorBanner>Fehler: {(e1 || e2) as string}</ErrorBanner>}

      {mfrr && <KPIs mfrr={mfrr} />}
      {mfrr && <MfrrTable rows={mfrr} />}
      {survey && <SurveyList rows={survey} />}
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