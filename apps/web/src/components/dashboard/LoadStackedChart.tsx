import React, { useMemo } from "react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend,
} from "recharts";
import { nf2 } from "../../lib/units";

type Row = Record<string, any> & {
  timestamp: string;
  total_mw?: number;
};

type Props = {
  data: Row[];
  mode: "stacked" | "sum";
  deviceKeys: string[];  // z.B. ["Geschirrspüler", "Backofen und Herd", ...]
};

export default function LoadStackedChart({ data, mode, deviceKeys }: Props) {
  const series = useMemo(() => {
    return data.map((r) => {
      const t = r.timestamp.slice(0, 16).replace("T", " ");
      const obj: Record<string, number | string> = { t };
      let sum = 0;
      for (const k of deviceKeys) {
        const v = typeof r[k] === "number" ? (r[k] as number) : 0;
        obj[k] = v;
        sum += v;
      }
      obj["sum"] = sum;
      return obj;
    });
  }, [data, deviceKeys]);

  return (
    <div className="w-full h-80 rounded-2xl border p-3 shadow-sm bg-white">
      <div className="text-sm font-medium mb-1">
        Lastprofil – {mode === "stacked" ? "gestapelt nach Geräten" : "aggregiert"}
      </div>
      <ResponsiveContainer width="100%" height="95%">
        <AreaChart data={series}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="t" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 12 }} width={60} />
          <Tooltip
            formatter={(val) => [nf2.format(val as number), "MW"]}
            labelFormatter={(l) => `Zeit: ${l}`}
          />
          <Legend />
          {mode === "stacked"
            ? deviceKeys.map((k) => (
                <Area key={k} dataKey={k} stackId="1" type="monotone" />
              ))
            : <Area dataKey="sum" type="monotone" strokeWidth={2} />}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
