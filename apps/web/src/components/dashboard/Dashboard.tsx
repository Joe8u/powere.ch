import React, { useEffect, useMemo, useState } from 'react';
import { useMfrr } from './hooks/useMfrr';
import { useSurvey } from './hooks/useSurvey';
import { useLastprofile, useLastprofileGroups } from './hooks/useLastprofile';
import { fetchMfrrLatest } from './api/warehouse';
import { KPIs } from './sections/KPIs';
import { MfrrTable } from './sections/MfrrTable';
import { SurveyList } from './sections/SurveyList';
import { Loading } from './ui/Loading';
import { ErrorBanner } from './ui/ErrorBanner';
import type { Agg } from './types';
import { Suspense, lazy } from 'react';
const MfrrChart = lazy(() => import('./sections/MfrrChart'));
const LastprofileChart = lazy(() => import('./sections/LastprofileChart'));

export default function Dashboard() {
  // Filter-State
  const [agg, setAgg] = useState<Agg>('hour');
  const [days, setDays] = useState<number>(1);
  const [lpSel, setLpSel] = useState<string[]>([]);
  const [fromVal, setFromVal] = useState<string>('');  // 'YYYY-MM-DDTHH:mm'
  const [toVal, setToVal] = useState<string>('');      // 'YYYY-MM-DDTHH:mm'

  // Limit passend zur Aggregation / Zeitraum
  const limit = useMemo(() => {
    if (fromVal && toVal) {
      const from = new Date(fromVal).getTime();
      const to = new Date(toVal).getTime();
      const diff = Math.max(0, to - from);
      if (agg === 'raw') return Math.max(1, Math.ceil(diff / (15 * 60 * 1000)));
      if (agg === 'hour') return Math.max(1, Math.ceil(diff / (60 * 60 * 1000)));
      return Math.max(1, Math.ceil(diff / (24 * 60 * 60 * 1000)));
    }
    if (agg === 'raw') return 96 * days;
    if (agg === 'hour') return 24 * days;
    return days;
  }, [agg, days, fromVal, toVal]);

  // Gemeinsamer Zeitraum (jetzt - days → jetzt)
  const [endOverride, setEndOverride] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    fetchMfrrLatest().then((ts) => { if (alive) setEndOverride(ts); }).catch(() => {});
    return () => { alive = false };
  }, []);

  // Hilfsformatierer für <input type="datetime-local">
  const toLocalInput = (d: Date) => {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  // initiale Vorbelegung anhand latest ts
  useEffect(() => {
    if (!endOverride) return;
    if (!toVal) setToVal(toLocalInput(new Date(endOverride)));
    if (!fromVal) {
      const end = new Date(endOverride);
      const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);
      setFromVal(toLocalInput(start));
    }
  }, [endOverride]);

  const startIso = fromVal ? new Date(fromVal).toISOString() : undefined;
  const endIso = toVal ? new Date(toVal).toISOString() : undefined;

  // Daten laden
  const { data: mfrr, loading: l1, error: e1 } = useMfrr({ agg, start: startIso, end: endIso, limit });
  const { data: survey, loading: l2, error: e2 } = useSurvey();
  const { groups: lpGroups } = useLastprofileGroups();
  const { rows: lastp, loading: l3, error: e3 } = useLastprofile({ agg, start: startIso, end: endIso, limit, columns: lpSel.join(',') });

  const loading = l1 || l2 || l3;
  const error = e1 || e2 || e3;

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
          Von:{' '}
          <input type="datetime-local" value={fromVal} onChange={(e) => setFromVal(e.target.value)} />
        </label>
        <label>
          Bis:{' '}
          <input type="datetime-local" value={toVal} onChange={(e) => setToVal(e.target.value)} />
        </label>
        <label>
          Schnellauswahl:{' '}
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={1}>letzte 24h</option>
            <option value={3}>letzte 3 Tage</option>
            <option value={7}>letzte 7 Tage</option>
            <option value={30}>letzte 30 Tage</option>
          </select>
        </label>
        <button onClick={() => {
          const base = endOverride ? new Date(endOverride) : new Date();
          const start = new Date(base.getTime() - days * 24 * 60 * 60 * 1000);
          setToVal(toLocalInput(base));
          setFromVal(toLocalInput(start));
        }}>Setzen</button>
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

      {/* Lastprofile Auswahl + Chart */}
      <section>
        <h3>Lastprofile</h3>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
          {(lpGroups || []).map((g) => (
            <label key={g} style={{ fontSize: 13 }}>
              <input
                type="checkbox"
                checked={lpSel.includes(g)}
                onChange={(e) => {
                  setLpSel((prev) => e.target.checked ? [...prev, g] : prev.filter((x) => x !== g));
                }}
              />{' '}{g}
            </label>
          ))}
        </div>
        <Suspense fallback={<div style={{height:260, border:'1px solid #eee', borderRadius:8}} />}>
          {lastp?.length && lpSel.length ? (
            <LastprofileChart rows={lastp} series={lpSel} />
          ) : (
            <div style={{height:260}} />
          )}
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
