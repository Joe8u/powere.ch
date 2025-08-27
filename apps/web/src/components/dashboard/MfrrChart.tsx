import React from "react";
import {
  ResponsiveContainer, ComposedChart, Bar, Line,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend, ReferenceLine,
} from "recharts";
import { chfKwhToEurMwh, eur, nf2 } from "../../lib/units";

type Row = { ts: string; total_called_mw: number; avg_price_eur_mwh: number };
type Props = {
  data: Row[];
  chfThresholdKwh: number;     // z.B. 0.29
  fxEurChf: number;            // z.B. 1.0
};

export default function MfrrChart({ data, chfThresholdKwh, fxEurChf }: Props) {
  const thrEurMwh = chfKwhToEurMwh(chfThresholdKwh, fxEurChf);

  const series = data.map((d) => ({
    t: d.ts.slice(0, 10),
    mw: d.total_called_mw ?? 0,
    price: d.avg_price_eur_mwh ?? 0,
  }));

  return (
    <div className="w-full h-80 rounded-2xl border p-3 shadow-sm bg-white">
      <div className="text-sm font-medium mb-1">
        mFRR: Aufrufe (MW) & Ø-Preis (EUR/MWh)
      </div>
      <ResponsiveContainer width="100%" height="95%">
        <ComposedChart data={series}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="t" tick={{ fontSize: 12 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 12 }} width={60} />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 12 }}
            width={70}
          />
          <Tooltip
            formatter={(val, name) => {
              if (name === "mw") return [nf2.format(val as number), "Called MW"];
              if (name === "price") return [eur.format(val as number), "Ø Preis"];
              return [String(val), name as string];
            }}
            labelFormatter={(l) => `Datum: ${l}`}
          />
          <Legend />
          <Bar yAxisId="left" dataKey="mw" name="Called MW" />
          <Line
            yAxisId="right"
            dataKey="price"
            name="Ø Preis (EUR/MWh)"
            dot={false}
            strokeWidth={2}
          />
          <ReferenceLine
            yAxisId="right"
            y={thrEurMwh}
            strokeDasharray="4 4"
            stroke="#666"
            label={{
              value: `Schwelle ≈ ${eur.format(thrEurMwh)}`,
              position: "insideTopRight",
              fontSize: 12,
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
