"use client";

import { useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { Heatmap } from "@/components/Heatmap";
import { MainChart } from "@/components/MainChart";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { Watchlist } from "@/components/Watchlist";
import { useChat } from "@/hooks/useChat";
import { usePortfolio } from "@/hooks/usePortfolio";
import { usePortfolioHistory } from "@/hooks/usePortfolioHistory";
import { usePriceStream } from "@/hooks/usePriceStream";
import { useWatchlist } from "@/hooks/useWatchlist";
import { computeLiveValuation } from "@/lib/portfolio";

export default function Home() {
  const { prices, connectionState, sparklines } = usePriceStream();
  const portfolio = usePortfolio();
  const history = usePortfolioHistory();
  const watchlist = useWatchlist();
  const chat = useChat();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  const valuation = computeLiveValuation(portfolio.portfolio, prices);

  function refreshAfterAction() {
    void portfolio.refetch();
    void watchlist.refetch();
    void history.refetch();
  }

  return (
    <div className="flex h-dvh flex-col bg-base-plane">
      <Header
        totalValue={valuation.totalValue}
        startingCash={portfolio.portfolio?.starting_cash ?? 10000}
        cashBalance={portfolio.portfolio?.cash_balance ?? 0}
        connectionState={connectionState}
        hasUnavailable={valuation.hasUnavailable}
      />

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[280px_1fr_340px]">
        <aside className="min-h-0 border-b border-line lg:border-b-0 lg:border-r">
          <Watchlist
            tickers={watchlist.tickers}
            prices={prices}
            sparklines={sparklines}
            selectedTicker={selectedTicker}
            onSelect={setSelectedTicker}
            onAdd={watchlist.add}
            onRemove={watchlist.remove}
          />
        </aside>

        <main className="grid min-h-0 grid-rows-[minmax(280px,1.3fr)_auto_minmax(260px,1fr)]">
          <div className="min-h-0 border-b border-line">
            <MainChart ticker={selectedTicker} latestUpdate={selectedTicker ? prices[selectedTicker] : undefined} />
          </div>

          <TradeBar selectedTicker={selectedTicker} prices={prices} onTraded={refreshAfterAction} />

          <div className="grid min-h-0 grid-cols-1 divide-line border-t border-line md:grid-cols-[1.2fr_1fr_1fr] md:divide-x">
            <div className="min-h-0 border-b border-line md:border-b-0">
              <PositionsTable positions={valuation.positions} onSelect={setSelectedTicker} />
            </div>
            <div className="min-h-0 border-b border-line md:border-b-0">
              <Heatmap positions={valuation.positions} />
            </div>
            <div className="min-h-0">
              <PnlChart snapshots={history.snapshots} startingCash={portfolio.portfolio?.starting_cash ?? 10000} />
            </div>
          </div>
        </main>

        <aside className="min-h-0 border-t border-line lg:border-l lg:border-t-0">
          <ChatPanel messages={chat.messages} loading={chat.loading} onSend={chat.send} onActionsExecuted={refreshAfterAction} />
        </aside>
      </div>
    </div>
  );
}
