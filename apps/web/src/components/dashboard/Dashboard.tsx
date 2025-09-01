import React, { useMemo, useState } from 'react';
import { useMfrr } from './hooks/useMfrr';
import { useSurvey } from './hooks/useSurvey';
import { KPIs } from './sections/KPIs';
import { MfrrTable } from './sections/MfrrTable';
import MfrrChart from './sections/MfrrChart';
import { SurveyList } from './sections/SurveyList';
import { Loading } from './ui/Loading';
import { ErrorBanner } from './ui/ErrorBanner';
import type { Agg } from './types';

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

  if (loading) return <Loading />;                    // <-- kein label-Prop
  if (error)   return <ErrorBanner>{error}</ErrorBanner>; // <-- erwartet children

  return (
    <div style={{ display: 'grid', gap: 16 }}>
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
      <MfrrChart data={mfrr ?? []} />

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