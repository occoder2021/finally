"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCurrency, formatDateTime } from "@/lib/format";
import type { Snapshot } from "@/lib/types";

interface PnlChartProps {
  snapshots: Snapshot[];
  startingCash: number;
}

export function PnlChart({ snapshots, startingCash }: PnlChartProps) {
  const data = snapshots.map((s) => ({
    t: new Date(s.recorded_at).getTime(),
    value: s.total_value,
  }));
  const positive = data.length > 0 && data[data.length - 1]!.value >= startingCash;
  const stroke = positive ? "#17c964" : "#e5484d";

  return (
    <section data-testid="pnl-chart" className="flex h-full flex-col">
      <h2 className="px-3 pb-2 pt-3 text-[13px] font-semibold text-ink-primary">Portfolio value</h2>
      <div className="min-h-0 flex-1 px-1 pb-2">
        {data.length < 2 ? (
          <div className="grid h-full place-items-center text-[12px] text-ink-muted">
            History will appear once a few snapshots have been recorded.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1a2030" vertical={false} />
              <XAxis
                dataKey="t"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(v: number) => formatDateTime(v)}
                stroke="#565f75"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: "#232a3b" }}
                minTickGap={40}
              />
              <YAxis
                dataKey="value"
                domain={["auto", "auto"]}
                tickFormatter={(v: number) => formatCurrency(v)}
                stroke="#565f75"
                fontSize={10}
                width={72}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<PnlTooltip />} />
              <Area type="monotone" dataKey="value" stroke={stroke} strokeWidth={2} fill="url(#pnlFill)" dot={false} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

function PnlTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { t: number; value: number } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]!.payload;
  return (
    <div className="rounded border border-line bg-base-overlay px-2.5 py-1.5 text-[11px] shadow-lg">
      <div className="tnum font-mono text-ink-primary">{formatCurrency(d.value)}</div>
      <div className="text-ink-secondary">{formatDateTime(d.t)}</div>
    </div>
  );
}
