import React, { useEffect, useMemo, useState } from 'react';
import { useSurvey } from './hooks/useSurvey';
import { useLastprofileGroups } from './hooks/useLastprofile';
import { useJoined } from './hooks/useJoined';
import { fetchMfrrLatest } from './api/warehouse';
import { KPIs } from './sections/KPIs';
import ControlPanel from './ControlPanel';
import { MfrrTable } from './sections/MfrrTable';
import { createPortal } from 'react-dom';
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
  const [showMw, setShowMw] = useState<boolean>(true);
  const [showPrice, setShowPrice] = useState<boolean>(true);

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
  const { data: joined, loading: l1, error: e1 } = useJoined({ agg, start: startIso, end: endIso, limit, columns: lpSel.join(',') });
  const { data: survey, loading: l2, error: e2 } = useSurvey();
  const { groups: lpGroups } = useLastprofileGroups();
  const lastp = joined; // joined liefert die gewünschten LP-Serien

  // Standard-Auswahl: beim ersten Laden "Geschirrspüler" (falls vorhanden), sonst erste Gruppe
  useEffect(() => {
    if (!lpGroups || lpGroups.length === 0) return;
    if (lpSel.length > 0) return; // Nutzer hat schon gewählt
    const preferred = lpGroups.find((g) => g.toLowerCase() === 'geschirrspüler') || lpGroups[0];
    if (preferred) setLpSel([preferred]);
  }, [lpGroups]);

  const loading = l1 || l2;
  const error = e1 || e2;
  const mfrrRows = useMemo(() => (joined ?? []).map(r => ({
    ts: String((r as any).ts ?? r['ts']),
    total_called_mw: Number((r as any).total_called_mw ?? 0),
    avg_price_eur_mwh: (r as any).avg_price_eur_mwh ?? null,
  })), [joined]);

  const [sidebarEl, setSidebarEl] = useState<HTMLElement | null>(null);
  useEffect(() => {
    const targetId = 'dashboard-right-panel';
    const initial = document.getElementById(targetId);
    if (initial) {
      setSidebarEl(initial);
      return;
    }
    const obs = new MutationObserver(() => {
      const el = document.getElementById(targetId);
      if (el) {
        setSidebarEl(el);
        obs.disconnect();
      }
    });
    obs.observe(document.documentElement, { childList: true, subtree: true });
    return () => obs.disconnect();
  }, []);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: sidebarEl ? 'minmax(0,1fr)' : 'minmax(0,1fr) 320px', gap: 16, alignItems: 'start' }}>
      <div style={{ display: 'grid', gap: 16 }}>
        {error && <ErrorBanner>{error}</ErrorBanner>}
        {loading && !joined && !survey && <Loading>Initialisiere…</Loading>}
        <KPIs mfrr={mfrrRows} />
        <section>
          <h3>mFRR (Chart)</h3>
          <Suspense fallback={<div style={{height:240, border:'1px solid #eee', borderRadius:8}} />}>
            {mfrrRows.length ? (
              <MfrrChart rows={mfrrRows} showMw={showMw} showPrice={showPrice} />
            ) : <div style={{height:240}} />}
          </Suspense>
        </section>
        <section>
          <h3>Lastprofile</h3>
          <Suspense fallback={<div style={{height:260, border:'1px solid #eee', borderRadius:8}} />}>
            {lastp?.length && lpSel.length ? (
              <LastprofileChart rows={lastp} series={lpSel} />
            ) : (
              <div style={{height:260}} />
            )}
          </Suspense>
        </section>
        <MfrrTable rows={mfrrRows} />
        <section>
          <h3>Survey (Beispiel: 5 Zeilen)</h3>
          <SurveyList rows={survey ?? []} />
        </section>
      </div>
      {sidebarEl
        ? createPortal(
            <ControlPanel
              showHeader={false}
              agg={agg}
              onAggChange={(a) => setAgg(a)}
              fromVal={fromVal}
              toVal={toVal}
              onFromChange={setFromVal}
              onToChange={setToVal}
              days={days}
              onDaysChange={setDays}
              onQuickSet={() => {
                const base = endOverride ? new Date(endOverride) : new Date();
                const start = new Date(base.getTime() - days * 24 * 60 * 60 * 1000);
                setToVal(toLocalInput(base));
                setFromVal(toLocalInput(start));
              }}
              showMw={showMw}
              onShowMw={setShowMw}
              showPrice={showPrice}
              onShowPrice={setShowPrice}
              lpGroups={lpGroups || []}
              lpSel={lpSel}
              onToggleGroup={(g, checked) => setLpSel((prev) => (checked ? [...prev, g] : prev.filter((x) => x !== g)))}
            />,
            sidebarEl
          )
        : <ControlPanel
        showHeader={true}
        agg={agg}
        onAggChange={(a) => setAgg(a)}
        fromVal={fromVal}
        toVal={toVal}
        onFromChange={setFromVal}
        onToChange={setToVal}
        days={days}
        onDaysChange={setDays}
        onQuickSet={() => {
          const base = endOverride ? new Date(endOverride) : new Date();
          const start = new Date(base.getTime() - days * 24 * 60 * 60 * 1000);
          setToVal(toLocalInput(base));
          setFromVal(toLocalInput(start));
        }}
        showMw={showMw}
        onShowMw={setShowMw}
        showPrice={showPrice}
        onShowPrice={setShowPrice}
        lpGroups={lpGroups || []}
        lpSel={lpSel}
        onToggleGroup={(g, checked) => setLpSel((prev) => checked ? [...prev, g] : prev.filter((x) => x !== g))}
      />}
    </div>
  );
}
