import React, { useEffect, useMemo, useState } from "react";
import MfrrChart from "./MfrrChart";
import LoadStackedChart from "./LoadStackedChart";
import MfrrCalendarHeatmap from "./MfrrCalendarHeatmap";
import { API_BASE } from "../../lib/config";
import { chfKwhToEurMwh, eur, nf2, two } from "../../lib/units";

type MfrrDay = { ts: string; total_called_mw: number; avg_price_eur_mwh: number };
type LastRow = Record<string, any> & { timestamp: string; total_mw?: number };

const DEFAULT_DEVICES = [
  "Geschirrspüler",
  "Backofen und Herd",
  "Fernseher und Entertainment-Systeme",
  "Bürogeräte",
  "Waschmaschine",
];

export default function Dashboard() {
  const [year, setYear] = useState<number>(2024);
  const [month, setMonth] = useState<number>(1);
  const [aggMfrr, setAggMfrr] = useState<"day" | "hour">("day");

  const [thresholdChfKwh, setThresholdChfKwh] = useState<number>(0.29);
  const [fxEurChf, setFxEurChf] = useState<number>(1.0);
  const [loadMode, setLoadMode] = useState<"stacked" | "sum">("stacked");

  const [mfrrYear, setMfrrYear] = useState<MfrrDay[]>([]);
  const [lastRows, setLastRows] = useState<LastRow[]>([]);
  const [deviceKeys, setDeviceKeys] = useState<string[]>(DEFAULT_DEVICES);

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Daten laden
  useEffect(() => {
    let aborted = false;
    const fetchAll = async () => {
      setLoading(true);
      setErr(null);
      try {
        // mFRR für ganzes Jahr (agg=day) – genügt für Chart/Heatmap
        const startY = new Date(year, 0, 1);
        const endY = new Date(year, 11, 31, 23, 59, 59);
        const pY = new URLSearchParams({
          agg: "day",
          start: startY.toISOString(),
          end: endY.toISOString(),
          limit: "100000",
        });
        const mfrrRes = await fetch(`${API_BASE}/warehouse/regelenergie/tertiary?${pY}`);
        if (!mfrrRes.ok) throw new Error(`mFRR failed: ${mfrrRes.status}`);
        const mfrrJson = (await mfrrRes.json()) as MfrrDay[];
        if (!aborted) setMfrrYear(mfrrJson);

        // Lastprofile: ein Monat (raw 15-min)
        const pL = new URLSearchParams({
          year: String(year),
          month: two(month),
          limit: "20000",
        });
        const lastRes = await fetch(`${API_BASE}/warehouse/lastprofile?${pL}`);
        if (!lastRes.ok) throw new Error(`lastprofile failed: ${lastRes.status}`);
        const lastJson = (await lastRes.json()) as LastRow[];
        if (!aborted) {
          setLastRows(lastJson);
          // Device-Spalten heuristisch bestimmen
          const sample = lastJson[0] || {};
          const keys = Object.keys(sample).filter(
            (k) =>
              !["timestamp", "year", "month", "total_mw"].includes(k) &&
              typeof sample[k] === "number"
          );
          if (keys.length > 0) setDeviceKeys(keys);
        }
      } catch (e: any) {
        if (!aborted) setErr(e?.message || String(e));
      } finally {
        if (!aborted) setLoading(false);
      }
    };
    fetchAll();
    return () => {
      aborted = true;
    };
  }, [year, month]);

  const mfrrMonth = useMemo(() => {
    const mm = two(month);
    return mfrrYear.filter((r) => (r.ts || "").slice(5, 7) === mm);
  }, [mfrrYear, month]);

  // KPIs
  const kpis = useMemo(() => {
    // mFRR (weighted Ø über Monatsdaten)
    const mwSum = mfrrMonth.reduce((a, r) => a + (r.total_called_mw || 0), 0);
    const priceW = mfrrMonth.reduce(
      (a, r) => a + (r.avg_price_eur_mwh || 0) * (r.total_called_mw || 0),
      0
    );
    const avgWeighted = mwSum > 0 ? priceW / mwSum : 0;
    const dayMax = mfrrMonth.reduce(
      (a, r) => Math.max(a, r.avg_price_eur_mwh || 0),
      0
    );

    // Load: Peak + Zeitpunkt + Top-Gerät
    let peak = 0;
    let peakAt: string | null = null;
    let peakTopDevice: string | null = null;
    for (const r of lastRows) {
      const total = typeof r.total_mw === "number"
        ? r.total_mw
        : deviceKeys.reduce((s, k) => s + (typeof r[k] === "number" ? r[k] : 0), 0);
      if (total > peak) {
        peak = total;
        peakAt = r.timestamp;
        // Top-Gerät am Peak
        let topK: string | null = null;
        let topV = -1;
        for (const k of deviceKeys) {
          const v = typeof r[k] === "number" ? r[k] : 0;
          if (v > topV) { topV = v; topK = k; }
        }
        peakTopDevice = topK;
      }
    }

    return {
      mwSum,
      avgWeighted,
      dayMax,
      peak,
      peakAt,
      peakTopDevice,
    };
  }, [mfrrMonth, lastRows, deviceKeys]);

  const thrEurMwh = chfKwhToEurMwh(thresholdChfKwh, fxEurChf);

  return (
    <div className="max-w-[1400px] mx-auto p-4 space-y-4">
      {/* Header / Filterbar */}
      <div className="rounded-2xl border p-4 bg-white shadow-sm">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-sm font-medium">Jahr</label>
            <select
              className="border rounded-md px-2 py-1"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            >
              {[2023, 2024, 2025].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium">Monat</label>
            <select
              className="border rounded-md px-2 py-1"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium">mFRR Aggregation</label>
            <select
              className="border rounded-md px-2 py-1"
              value={aggMfrr}
              onChange={(e) => setAggMfrr(e.target.value as any)}
            >
              <option value="day">Tag</option>
              <option value="hour" disabled>Stunde (bald)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium">Schwelle (CHF/kWh)</label>
            <input
              type="number" step="0.01" min="0"
              className="border rounded-md px-2 py-1 w-28"
              value={thresholdChfKwh}
              onChange={(e) => setThresholdChfKwh(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="block text-sm font-medium">FX EUR↔CHF</label>
            <input
              type="number" step="0.01" min="0.5" max="2"
              className="border rounded-md px-2 py-1 w-24"
              value={fxEurChf}
              onChange={(e) => setFxEurChf(Number(e.target.value))}
            />
          </div>

          <div>
            <label className="block text-sm font-medium">Last-Ansicht</label>
            <select
              className="border rounded-md px-2 py-1"
              value={loadMode}
              onChange={(e) => setLoadMode(e.target.value as any)}
            >
              <option value="stacked">Gestapelt</option>
              <option value="sum">Aggregiert</option>
            </select>
          </div>

          {loading && (
            <div className="text-sm text-gray-500">Lade Daten…</div>
          )}
          {err && (
            <div className="text-sm text-red-600">Fehler: {err}</div>
          )}
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="mFRR: Summe MW (Monat)" value={nf2.format(kpis.mwSum)} />
        <KpiCard
          label="mFRR: Ø (gewichtet)"
          value={eur.format(kpis.avgWeighted || 0)}
          hint={`≈ ${thresholdChfKwh} CHF/kWh ↔ ${eur.format(thrEurMwh)} EUR/MWh`}
        />
        <KpiCard label="mFRR: Tages-Ø-Max" value={eur.format(kpis.dayMax || 0)} />
        <KpiCard
          label="Last: Peak (MW)"
          value={nf2.format(kpis.peak || 0)}
          hint={kpis.peakAt ? new Date(kpis.peakAt).toLocaleString("de-CH") : "—"}
        />
      </div>

      {/* Hauptcharts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MfrrChart
          data={mfrrMonth}
          chfThresholdKwh={thresholdChfKwh}
          fxEurChf={fxEurChf}
        />
        <LoadStackedChart
          data={lastRows}
          mode={loadMode}
          deviceKeys={deviceKeys}
        />
      </div>

      {/* Heatmap (Jahr) */}
      <MfrrCalendarHeatmap
        year={year}
        dataYear={mfrrYear}
        thresholdEurMwh={thrEurMwh}
      />
    </div>
  );
}

function KpiCard(props: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border p-4 shadow-sm bg-white">
      <div className="text-xs text-gray-600">{props.label}</div>
      <div className="text-2xl font-semibold">{props.value}</div>
      {props.hint && <div className="text-[11px] text-gray-500 mt-1">{props.hint}</div>}
    </div>
  );
}
