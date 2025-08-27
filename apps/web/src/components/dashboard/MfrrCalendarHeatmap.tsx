import React, { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { monthNames } from "../../lib/units";

// Erwartet: komplette Jahresreihe (agg=day) – wir zeichnen 12×31 Grid (Ø-Preis pro Tag)
type Row = { ts: string; avg_price_eur_mwh: number | null };

type Props = {
  year: number;
  dataYear: Row[];              // alle Tage des Jahres (Ø EUR/MWh, aktuell)
  thresholdEurMwh: number;      // horizontale Schwelle (nur für Legende/Hinweis)
};

export default function MfrrCalendarHeatmap({ year, dataYear, thresholdEurMwh }: Props) {
  // Map: month(1..12) x day(1..31) -> value
  const grid = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of dataYear) {
      const d = new Date(r.ts);
      if (isNaN(d.getTime())) continue;
      if (d.getFullYear() !== year) continue;
      const m = d.getMonth() + 1;
      const day = d.getDate();
      if (typeof r.avg_price_eur_mwh === "number") {
        map.set(`${m}-${day}`, r.avg_price_eur_mwh);
      }
    }
    // ECharts heatmap expects [xIndex, yIndex, value]
    const xs = Array.from({ length: 31 }, (_, i) => i + 1);
    const ys = Array.from({ length: 12 }, (_, i) => i + 1);
    const data: [number, number, number | null][] = [];
    ys.forEach((m, yIdx) => {
      xs.forEach((day, xIdx) => {
        const v = map.get(`${m}-${day}`);
        data.push([xIdx, yIdx, v ?? null]);
      });
    });
    return data;
  }, [dataYear, year]);

  const option = {
    tooltip: {
      position: "top",
      formatter: (p: any) => {
        const day = p.value[0] + 1;
        const mon = p.value[1];
        const val = p.value[2];
        const d = `${year}-${String(mon).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
        if (val == null) return `${d}<br/>—`;
        return `${d}<br/>Ø Preis: ${val.toFixed(2)} EUR/MWh`;
      },
    },
    grid: { top: 10, right: 10, bottom: 20, left: 60 },
    xAxis: {
      type: "category",
      data: Array.from({ length: 31 }, (_, i) => String(i + 1)),
      splitArea: { show: true },
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: "category",
      data: monthNames,
      splitArea: { show: true },
      axisLabel: { fontSize: 11 },
    },
    visualMap: {
      min: 0,
      max: Math.max(300, ...grid.map((g) => (g[2] ?? 0))) || 300,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
    },
    series: [
      {
        name: "Ø Preis",
        type: "heatmap",
        data: grid,
        emphasis: { itemStyle: { borderColor: "#333", borderWidth: 1 } },
        progressive: 0,
        animation: false,
      },
    ],
  };

  return (
    <div className="w-full h-72 rounded-2xl border p-3 shadow-sm bg-white">
      <div className="text-sm font-medium mb-1">
        mFRR Preis-Heatmap (Ø pro Tag) – Jahr {year}
      </div>
      <ReactECharts option={option} style={{ height: "90%", width: "100%" }} />
      <div className="text-[11px] text-gray-500 mt-1">
        Hinweis: aktuell Ø-Preis pro Tag. Für “tägliches Maximum” ergänzen wir
        serverseitig <code>stat=max_price</code>.
      </div>
    </div>
  );
}
