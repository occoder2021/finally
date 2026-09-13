"use client";

import { formatCurrency, formatPercent, formatSignedCurrency } from "@/lib/format";
import type { ConnectionState } from "@/lib/types";

interface HeaderProps {
  totalValue: number;
  startingCash: number;
  cashBalance: number;
  connectionState: ConnectionState;
  hasUnavailable: boolean;
}

const STATE_LABEL: Record<ConnectionState, string> = {
  connected: "Live",
  connecting: "Reconnecting",
  disconnected: "Offline",
};

const STATE_DOT: Record<ConnectionState, string> = {
  connected: "bg-good shadow-[0_0_8px_theme(colors.good.DEFAULT)]",
  connecting: "bg-accent shadow-[0_0_8px_theme(colors.accent.DEFAULT)] animate-pulse",
  disconnected: "bg-critical shadow-[0_0_8px_theme(colors.critical.DEFAULT)]",
};

export function Header({ totalValue, startingCash, cashBalance, connectionState, hasUnavailable }: HeaderProps) {
  const totalReturn = totalValue - startingCash;
  const totalReturnPct = startingCash !== 0 ? (totalReturn / startingCash) * 100 : 0;
  const returnColor = totalReturn > 0 ? "text-good-text" : totalReturn < 0 ? "text-critical-text" : "text-ink-secondary";

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-base-panel px-4">
      <div className="flex items-center gap-2.5">
        <span className="grid h-6 w-6 place-items-center rounded-sm bg-accent text-[13px] font-bold text-base-plane">F</span>
        <span className="text-[15px] font-semibold tracking-tight text-ink-primary">FinAlly</span>
      </div>

      <div className="flex items-center gap-7">
        <Stat label="Cash" testId="cash-balance" value={formatCurrency(cashBalance)} />
        <Stat
          label="Total value"
          testId="total-value"
          value={formatCurrency(totalValue)}
          suffix={hasUnavailable ? <span title="One or more holdings have no live price right now" className="ml-1 text-accent">*</span> : null}
          emphasize
        />
        <Stat
          label="Return"
          testId="total-return"
          value={`${formatSignedCurrency(totalReturn)} (${formatPercent(totalReturnPct, { signed: true })})`}
          valueClassName={returnColor}
        />
      </div>

      <div className="flex items-center gap-2 text-[12px] text-ink-secondary" data-testid="connection-status" data-state={connectionState}>
        <span className={`h-2 w-2 rounded-full ${STATE_DOT[connectionState]}`} />
        {STATE_LABEL[connectionState]}
      </div>
    </header>
  );
}

function Stat({
  label,
  value,
  testId,
  emphasize,
  valueClassName,
  suffix,
}: {
  label: string;
  value: string;
  testId: string;
  emphasize?: boolean;
  valueClassName?: string;
  suffix?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="text-[10.5px] text-ink-muted">{label}</span>
      <span
        data-testid={testId}
        className={`tnum font-mono ${emphasize ? "text-[15px] font-semibold" : "text-[13px] font-medium"} ${valueClassName ?? "text-ink-primary"}`}
      >
        {value}
        {suffix}
      </span>
    </div>
  );
}
