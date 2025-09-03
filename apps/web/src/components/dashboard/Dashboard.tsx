import React, { useMemo, useState } from 'react';
import { useMfrr } from './hooks/useMfrr';
import { useSurvey } from './hooks/useSurvey';
import { KPIs } from './sections/KPIs';
import { MfrrTable } from './sections/MfrrTable';
import { SurveyList } from './sections/SurveyList';
import { Loading } from './ui/Loading';
import { ErrorBanner } from './ui/ErrorBanner';
import type { Agg } from './types';
import { Suspense, lazy } from 'react';
const MfrrChart = lazy(() => import('./sections/MfrrChart'));

export default function Dashboard() {
  // Filter-State
  const [agg, setAgg] = useState<Agg>('hour');
  const [days, setDays] = useState<number>(1);

  // Limit passend zur Aggregation
  const limit = useMemo(() => {
    if (agg === 'raw') return 96 * days;    // 96 Viertelstunden pro Tag
    if (agg === 'hour') return 24 * days;   // 24 Stunden pro Tag
    return days;                             // day-agg => 1 Punkt pro Tag
  }, [agg, days]);

  // Daten laden
  const { data: mfrr, loading: l1, error: e1 } = useMfrr({ agg, limit });
  const { data: survey, loading: l2, error: e2 } = useSurvey();

  const loading = l1 || l2;
  const error = e1 || e2;

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* Status */}
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {loading && !mfrr && !survey && <Loading>Initialisiere…</Loading>}
      {/* Filter */}
      <section style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <strong>Filter:</strong>
        <label>
          Aggregation:{' '}
          <select value={agg} onChange={(e) => setAgg(e.target.value as Agg)}>
            <option value="raw">15-Min</option>
            <option value="hour">Stunde</option>
            <option value="day">Tag</option>
          </select>
        </label>
        <label>
          Dauer:{' '}
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={1}>1 Tag</option>
            <option value={3}>3 Tage</option>
            <option value={7}>7 Tage</option>
            <option value={30}>30 Tage</option>
          </select>
        </label>
      </section>

      {/* KPIs */}
      <KPIs mfrr={mfrr ?? []} />

      {/* Chart */}
      <section>
        <h3>mFRR (Chart)</h3>
        <Suspense fallback={<div style={{height:240, border:'1px solid #eee', borderRadius:8}} />}>
          {mfrr?.length ? <MfrrChart rows={mfrr} /> : <div style={{height:240}} />}
        </Suspense>
      </section>

      {/* Tabelle */}
      <MfrrTable rows={mfrr ?? []} />     {/* <-- erwartet rows */}

      {/* Survey-Beispiel */}
      <section>
        <h3>Survey (Beispiel: 5 Zeilen)</h3>
        <SurveyList rows={survey ?? []} /> {/* <-- erwartet rows */}
      </section>
    </div>
  );
}