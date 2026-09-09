# Market Data Backend — Design

## Status

**This design is fully implemented** in `backend/app/market/`. Anyone extending or reviewing the market data code should treat this document as the contract.

The previously-outstanding items are now done:

| Item | Where |
|---|---|
| `day_open` on `PriceUpdate`, and the PLAN.md §6 wire keys (`prev_price`, `change_pct`) | `models.py` |
| Day-open reference tracked and preserved for the process lifetime | `cache.py` (`set_day_open` / `get_day_open`) |
| `PriceHistoryBuffer` — bounded per-ticker series | `history.py` |
| `MarketSinks` — one write call feeding both sinks | `sinks.py` |
| Both data sources writing through the sinks | `simulator.py`, `massive_client.py` |
| `GET /api/prices/{ticker}/history` | `prices_route.py` |
| Application wiring and lifespan | `app/main.py` |

Two deviations from the illustrative code below, both deliberate:

1. The history route lives at `app/market/prices_route.py`, not `app/routes/prices.py`, to sit beside the SSE router (`stream.py`) that already lives in the market package. Both are exported from `app.market`.
2. `create_stream_router()` builds its `APIRouter` inside the factory rather than at module scope, so repeated calls cannot stack duplicate routes onto a shared router.

The watchlist ∪ positions union (§9.1) is a **routes-layer** responsibility and still awaits the database layer. `app.main.initial_tickers()` currently returns the default watchlist and is the single call site to replace when that lands; the market package already supports it via `add_ticker`/`remove_ticker`.

---

## 1. Goals & Constraints

From `PLAN.md`:

- One background task produces prices (simulator by default, Massive REST poller if `MASSIVE_API_KEY` is set) — both must conform to the same interface so downstream code is source-agnostic.
- A single in-memory price cache holds the latest price, previous price, **day-open (seed) price**, and timestamp per ticker.
- SSE (`GET /api/stream/prices`) pushes updates for the **union of watchlist tickers and tickers with open positions**.
- A ~200-point in-memory history buffer per ticker feeds `GET /api/prices/{ticker}/history` for chart seeding.
- Tickers can be added/removed at runtime without a client reconnect.
- Adding a real data provider must not require changing the cache, SSE layer, portfolio valuation, or frontend contract — only swap the producer.

---

## 2. Architecture

```
                    ┌─────────────────────────────┐
                    │   create_market_data_source() │   (factory.py)
                    │   reads MASSIVE_API_KEY        │
                    └───────────┬─────────────────┘
                                │ returns one of:
              ┌─────────────────┴──────────────────┐
              ▼                                     ▼
   ┌────────────────────┐              ┌─────────────────────────┐
   │ SimulatorDataSource │              │   MassiveDataSource      │
   │  (GBM, 500ms tick)  │              │  (Polygon REST, 15s poll)│
   └──────────┬──────────┘              └────────────┬─────────────┘
              │  both implement MarketDataSource (ABC)  │
              │  both write to the same sinks:          │
              ▼                                         ▼
     ┌────────────────────────────────────────────────────────┐
     │                     PriceCache                          │
     │  latest price · previous price · timestamp per ticker   │
     └───────────────────────┬────────────────────────────────┘
                              │
     ┌────────────────────────────────────────────────────────┐
     │                  PriceHistoryBuffer                     │
     │   last ~200 (ticker, price, timestamp) points/ticker     │
     └───────────────────────┬────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  SSE /api/stream/prices  GET /api/prices/  Portfolio valuation &
  (watchlist ∪ positions)  {ticker}/history   trade execution
```

Both `SimulatorDataSource` and `MassiveDataSource` implement the abstract `MarketDataSource` interface (Strategy pattern). Neither the SSE endpoint, the history endpoint, nor the portfolio/trade code ever imports the simulator or the Massive client directly — they only depend on `PriceCache` / `PriceHistoryBuffer`, which are populated by whichever source `create_market_data_source()` selects. This is what makes "real data vs. simulated" a pure environment-variable switch.

---

## 3. Data Model — `PriceUpdate`

`backend/app/market/models.py`

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    day_open: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from the previous tick."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Tick-over-tick percentage change."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def day_change_percent(self) -> float:
        """Percentage change from the day-open (seed) reference price — PLAN.md §6 Decision #2."""
        if self.day_open == 0:
            return 0.0
        return round((self.price - self.day_open) / self.day_open * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat', based on tick-over-tick change."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize to the wire shape used by SSE (matches PLAN.md §6 field names)."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.previous_price,
            "day_open": self.day_open,
            "change_pct": self.day_change_percent,
            "timestamp": self.timestamp,
            "direction": self.direction,
        }
```

> **Design note (applied):** the original `PriceUpdate` omitted `day_open` and exposed only tick-over-tick `change_percent`, and `to_dict()` used the keys `previous_price` / `change_percent` rather than PLAN.md's `prev_price` / `change_pct`. The version above is now the shipped shape — it adds `day_open` as a required field (populated from `seed_prices.SEED_PRICES` for the simulator, and from the prior trading day's close for Massive) and renames the wire keys to match the PLAN.md §6 contract exactly: `ticker, price, prev_price, day_open, change_pct, timestamp, direction`. This was the one breaking change needed to close the gap between the code and the spec; everything else in this document was additive. Callers constructing a `PriceUpdate` directly must now pass `day_open`.

---

## 4. The Unified Interface — `MarketDataSource`

`backend/app/market/interface.py`

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache (and
    PriceHistoryBuffer) on their own schedule. Downstream code never calls
    the data source directly for prices — it reads from the cache/buffer.

    Lifecycle:
        source = create_market_data_source(cache, history)
        await source.start(["AAPL", "GOOGL", ...])
        # ... app runs ...
        await source.add_ticker("TSLA")
        await source.remove_ticker("GOOGL")
        # ... app shutting down ...
        await source.stop()
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.

        Starts a background task that periodically writes to the PriceCache.
        Must be called exactly once. Calling start() twice is undefined behavior.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources. Safe to call multiple times."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present.

        The next update cycle includes this ticker; no client reconnect needed
        (PLAN.md §6/§13 Decision #8).
        """

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set. No-op if not present.

        Also removes the ticker from the PriceCache. Caller is responsible for
        checking whether the ticker still has an open position before calling
        this — see §9 below on the watchlist ∪ positions union.
        """

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the current list of actively tracked tickers."""
```

Why an ABC and not a `Protocol`: both implementations are long-lived, stateful objects with an explicit lifecycle (`start`/`stop`), so nominal subclassing communicates intent better than structural typing here, and `abstractmethod` gives a hard failure at instantiation time if a new provider forgets a method.

---

## 5. Shared Sinks

### 5.1 `PriceCache` — latest price per ticker

`backend/app/market/cache.py`

```python
from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (exactly one at a time,
    selected by the factory). Readers: SSE endpoint, portfolio valuation,
    trade execution, watchlist endpoint.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._day_open: dict[str, float] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonic; bumped on every update, drives SSE change detection

    def set_day_open(self, ticker: str, price: float) -> None:
        """Record the day-open reference price for a ticker (called once, at source start
        or when a ticker is first added)."""
        with self._lock:
            self._day_open.setdefault(ticker, round(price, 2))

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price for a ticker. Returns the created PriceUpdate.

        Computes direction/change from the previous price, and change vs. the
        stored day-open. If no day-open is recorded yet, this price becomes it.
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price
            day_open = self._day_open.setdefault(ticker, round(price, 2))

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                day_open=day_open,
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Snapshot of all current prices. Returns a shallow copy (safe to iterate
        without holding the lock)."""
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._prices.pop(ticker, None)
            self._day_open.pop(ticker, None)

    @property
    def version(self) -> int:
        """Monotonic counter — SSE uses this to avoid re-serializing/pushing when nothing changed."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

A plain `threading.Lock` (not `asyncio.Lock`) is correct here: writes happen from the asyncio event loop (simulator tick, or the Massive poll callback after `asyncio.to_thread`), and reads can happen from sync contexts too (e.g., trade-execution validation called from a request handler). The critical sections are microseconds-long dict operations, so a blocking lock never stalls the event loop meaningfully.

### 5.2 `PriceHistoryBuffer` — recent history per ticker

`backend/app/market/history.py`

This is the piece needed to satisfy `GET /api/prices/{ticker}/history` (PLAN.md §6, §8, Decision #3): "The backend maintains a short in-memory price history buffer per ticker (last ~200 data points) ... populated by the same background task that writes to the price cache."

```python
from __future__ import annotations

from collections import deque
from threading import Lock

MAX_POINTS = 200


class PriceHistoryBuffer:
    """Thread-safe ring buffer of recent (timestamp, price) points per ticker.

    Written by the same call site that writes to PriceCache (see
    `record_price` helper in §5.3), so the two sinks never drift out of sync.
    """

    def __init__(self, max_points: int = MAX_POINTS) -> None:
        self._max_points = max_points
        self._buffers: dict[str, deque[tuple[float, float]]] = {}
        self._lock = Lock()

    def append(self, ticker: str, price: float, timestamp: float) -> None:
        with self._lock:
            buf = self._buffers.setdefault(ticker, deque(maxlen=self._max_points))
            buf.append((timestamp, price))

    def get(self, ticker: str) -> list[dict[str, float]]:
        """Return points oldest-first: [{"timestamp": ..., "price": ...}, ...]."""
        with self._lock:
            buf = self._buffers.get(ticker)
            if not buf:
                return []
            return [{"timestamp": ts, "price": price} for ts, price in buf]

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._buffers.pop(ticker, None)
```

`deque(maxlen=N)` is the right structure: O(1) append, automatically evicts the oldest point once full, no manual trimming logic, and no unbounded memory growth as the simulator runs for hours.

### 5.3 Wiring both sinks from one write call

To guarantee the cache and the history buffer never disagree, both data sources write through a single helper rather than calling `cache.update()` and `history.append()` separately at each call site:

```python
# backend/app/market/sinks.py
from __future__ import annotations

import time

from .cache import PriceCache
from .history import PriceHistoryBuffer
from .models import PriceUpdate


class MarketSinks:
    """Bundles PriceCache + PriceHistoryBuffer so data sources write to both
    atomically from the caller's point of view, with one call."""

    def __init__(self, cache: PriceCache, history: PriceHistoryBuffer) -> None:
        self.cache = cache
        self.history = history

    def record(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        ts = timestamp or time.time()
        update = self.cache.update(ticker=ticker, price=price, timestamp=ts)
        self.history.append(ticker=ticker, price=update.price, timestamp=ts)
        return update

    def remove(self, ticker: str) -> None:
        self.cache.remove(ticker)
        self.history.remove(ticker)
```

Both `SimulatorDataSource` and `MassiveDataSource` are constructed with a `MarketSinks` instance instead of a bare `PriceCache`, and call `self._sinks.record(...)` / `self._sinks.remove(...)` everywhere they currently call `self._cache.update(...)` / `self._cache.remove(...)`. This is a mechanical rename — no behavioral change to the cache-only logic already implemented.

---

## 6. Simulator (Default) — GBM with Correlated Moves

`backend/app/market/seed_prices.py` — starting prices, per-ticker drift/volatility, and sector correlation groups:

```python
# Realistic starting prices for the default watchlist — these also serve as
# the day-open reference price (PLAN.md §6 Decision #2).
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00, "GOOGL": 175.00, "MSFT": 420.00, "AMZN": 185.00,
    "TSLA": 250.00, "NVDA": 800.00, "META": 500.00, "JPM": 195.00,
    "V": 280.00, "NFLX": 600.00,
}

# sigma: annualized volatility. mu: annualized drift (expected return).
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL": {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT": {"sigma": 0.20, "mu": 0.05},
    "AMZN": {"sigma": 0.28, "mu": 0.05},
    "TSLA": {"sigma": 0.50, "mu": 0.03},   # High volatility
    "NVDA": {"sigma": 0.40, "mu": 0.08},   # High volatility, strong drift
    "META": {"sigma": 0.30, "mu": 0.05},
    "JPM":  {"sigma": 0.18, "mu": 0.04},   # Low volatility (bank)
    "V":    {"sigma": 0.17, "mu": 0.04},   # Low volatility (payments)
    "NFLX": {"sigma": 0.35, "mu": 0.05},
}

DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}  # dynamically-added tickers

CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}
INTRA_TECH_CORR = 0.6
INTRA_FINANCE_CORR = 0.5
CROSS_GROUP_CORR = 0.3
TSLA_CORR = 0.3   # TSLA does its own thing even though it's nominally "tech"
```

### 6.1 The math

Geometric Brownian Motion:

```
S(t+dt) = S(t) * exp((mu - sigma²/2) * dt + sigma * sqrt(dt) * Z)
```

- `S(t)` — current price
- `mu` — annualized drift
- `sigma` — annualized volatility
- `dt` — time step, as a fraction of a trading year
- `Z` — a (correlated) standard-normal random draw

With ticks every 500ms and 252 trading days × 6.5h/day of "market time" per year:

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600      # 5,896,800
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR       # ≈ 8.48e-8
```

That tiny `dt` produces sub-cent moves per tick which compound naturally into realistic-looking intraday drift and volatility over minutes of wall-clock time.

### 6.2 Correlated draws via Cholesky decomposition

Independent GBM per ticker would make a "tech selloff" look wrong — nothing would move together. To get correlated moves without simulating a full covariance model, build a correlation matrix from sector groupings and use its Cholesky factor to transform independent normal draws into correlated ones:

```python
import numpy as np

def _rebuild_cholesky(tickers: list[str], pairwise_corr) -> np.ndarray | None:
    n = len(tickers)
    if n <= 1:
        return None
    corr = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            rho = pairwise_corr(tickers[i], tickers[j])
            corr[i, j] = corr[j, i] = rho
    return np.linalg.cholesky(corr)

# Each tick:
z_independent = np.random.standard_normal(n)
z_correlated = cholesky @ z_independent if cholesky is not None else z_independent
```

`corr` is symmetric positive semi-definite by construction (1s on the diagonal, off-diagonal entries in `[0, 1)` from a fixed small set of values), so `np.linalg.cholesky` is safe here — it would only raise on a non-PSD matrix, which this construction cannot produce. Correlation lookup:

```python
@staticmethod
def _pairwise_correlation(t1: str, t2: str) -> float:
    tech = CORRELATION_GROUPS["tech"]
    finance = CORRELATION_GROUPS["finance"]
    if t1 == "TSLA" or t2 == "TSLA":
        return TSLA_CORR
    if t1 in tech and t2 in tech:
        return INTRA_TECH_CORR
    if t1 in finance and t2 in finance:
        return INTRA_FINANCE_CORR
    return CROSS_GROUP_CORR
```

Rebuilding the `n×n` Cholesky factor is `O(n³)` in the worst case, but `n` stays under ~50 tickers in practice, so it's cheap (~microseconds) even on every `add_ticker`/`remove_ticker` call — no need to amortize or cache it further.

### 6.3 One simulation step (the hot path — runs every 500ms)

```python
def step(self) -> dict[str, float]:
    n = len(self._tickers)
    if n == 0:
        return {}

    z_independent = np.random.standard_normal(n)
    z_correlated = self._cholesky @ z_independent if self._cholesky is not None else z_independent

    result: dict[str, float] = {}
    for i, ticker in enumerate(self._tickers):
        params = self._params[ticker]
        mu, sigma = params["mu"], params["sigma"]

        drift = (mu - 0.5 * sigma**2) * self._dt
        diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
        self._prices[ticker] *= math.exp(drift + diffusion)

        # Random "event": ~0.1% chance per tick per ticker → a sudden 2-5% move,
        # for visual drama (PLAN.md §6). At 10 tickers / 2 ticks-per-second,
        # expect roughly one event every ~50 seconds.
        if random.random() < self._event_prob:
            shock_magnitude = random.uniform(0.02, 0.05)
            shock_sign = random.choice([-1, 1])
            self._prices[ticker] *= 1 + shock_magnitude * shock_sign

        result[ticker] = round(self._prices[ticker], 2)

    return result
```

### 6.4 `SimulatorDataSource` — the async wrapper

```python
class SimulatorDataSource(MarketDataSource):
    def __init__(self, sinks: MarketSinks, update_interval: float = 0.5,
                 event_probability: float = 0.001) -> None:
        self._sinks = sinks
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)
        # Seed both sinks immediately so SSE/history have data before the first tick.
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._sinks.cache.set_day_open(ticker, price)
                self._sinks.record(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            price = self._sim.get_price(ticker)
            if price is not None:
                self._sinks.cache.set_day_open(ticker, price)
                self._sinks.record(ticker=ticker, price=price)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._sinks.remove(ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        while True:
            try:
                if self._sim:
                    for ticker, price in self._sim.step().items():
                        self._sinks.record(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

The `try/except Exception` around the step body is deliberate: one bad tick (e.g., a NaN from a pathological `sigma`) must never kill the background task — the loop logs and keeps going on the next interval, since a dead price feed is a much worse user experience than one skipped/odd tick.

---

## 7. Massive (Polygon.io) — Real Market Data

`backend/app/market/massive_client.py`

Selected only when `MASSIVE_API_KEY` is set (see the factory in §8). Uses REST polling — not a WebSocket — because it works uniformly on every Polygon/Massive pricing tier, including the free one.

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

class MassiveDataSource(MarketDataSource):
    """Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all watched
    tickers in one API call, then writes results into the shared sinks.

    Rate limits: free tier is 5 req/min -> poll_interval=15s (default).
    Paid tiers support 2-5s polling.
    """

    def __init__(self, api_key: str, sinks: MarketSinks, poll_interval: float = 15.0) -> None:
        self._api_key = api_key
        self._sinks = sinks
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)
        await self._poll_once()   # immediate first poll so the cache isn't empty
        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)   # appears automatically on the next poll

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._sinks.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        if not self._tickers or not self._client:
            return
        try:
            # The Massive RESTClient is synchronous — offload to a thread so a
            # slow HTTP call never blocks the event loop (and thus the SSE stream).
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            for snap in snapshots:
                try:
                    price = snap.last_trade.price
                    timestamp = snap.last_trade.timestamp / 1000.0  # ms -> s
                    if snap.ticker not in self._sinks.cache:
                        # First time seeing this ticker: previous day's close is
                        # the day-open reference (falls back to first price seen
                        # if the field is unavailable).
                        day_open = getattr(snap, "prev_day", None)
                        day_open = getattr(day_open, "close", price) if day_open else price
                        self._sinks.cache.set_day_open(snap.ticker, day_open)
                    self._sinks.record(ticker=snap.ticker, price=price, timestamp=timestamp)
                except (AttributeError, TypeError) as e:
                    logger.warning("Skipping snapshot for %s: %s", getattr(snap, "ticker", "???"), e)
        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # Don't re-raise: 401 (bad key), 429 (rate limit), and network errors
            # should not kill the poller — just retry on the next interval.

    def _fetch_snapshots(self) -> list:
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

Same `MarketDataSource` shape as the simulator, same failure-isolation philosophy (log and continue rather than crash the poller), same `MarketSinks` write path — this is what "one interface, two producers" buys: the SSE endpoint, the history endpoint, and the portfolio code cannot tell which one is running.

---

## 8. Factory — Environment-Driven Selection

`backend/app/market/factory.py`

```python
import os

def create_market_data_source(sinks: MarketSinks) -> MarketDataSource:
    """MASSIVE_API_KEY set and non-empty -> MassiveDataSource (real data).
    Otherwise -> SimulatorDataSource (GBM simulation). Returns an unstarted
    source; caller must await source.start(tickers)."""
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, sinks=sinks)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(sinks=sinks)
```

This is the **entire** mechanism PLAN.md §5 describes as "Environment-variable driven — simulator by default, real data via Massive API if key provided." No feature flags, no config file, no runtime toggle — one env var, checked once at startup.

---

## 9. SSE Streaming Endpoint

`backend/app/market/stream.py`

Endpoint contract (PLAN.md §6/§8): `GET /api/stream/prices`, long-lived, native `EventSource` on the client, each event a JSON object keyed by ticker, each value shaped per `PriceUpdate.to_dict()` (§3 above): `ticker, price, prev_price, day_open, change_pct, timestamp, direction`.

```python
router = APIRouter(prefix="/api/stream", tags=["streaming"])

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # disable proxy buffering (nginx et al.)
            },
        )
    return router


async def _generate_events(price_cache: PriceCache, request: Request,
                            interval: float = 0.5) -> AsyncGenerator[str, None]:
    yield "retry: 1000\n\n"   # EventSource auto-reconnect delay if the connection drops

    last_version = -1
    try:
        while True:
            if await request.is_disconnected():
                break

            current_version = price_cache.version
            if current_version != last_version:      # skip the write if nothing changed
                last_version = current_version
                prices = price_cache.get_all()
                if prices:
                    payload = json.dumps({t: u.to_dict() for t, u in prices.items()})
                    yield f"data: {payload}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
```

The `version` counter (bumped on every `PriceCache.update()`) is what makes this cheap: polling every 500ms costs nothing when the simulator hasn't ticked yet (e.g., between Massive polls, which are much slower than the 500ms SSE loop) — the endpoint just compares an int and sleeps again instead of re-serializing and re-sending unchanged data.

### 9.1 Restricting the SSE feed to watchlist ∪ open positions

PLAN.md §6 requires the stream to cover the **union** of watchlist tickers and tickers with open positions, not simply "every ticker the data source happens to be tracking" — a position in a ticker removed from the watchlist must keep receiving price updates for P&L. This filtering belongs at the API layer (which owns the DB-backed watchlist/positions tables), not inside the market package:

```python
# backend/app/routes/portfolio.py (illustrative — outside app/market/)
async def _visible_tickers(db) -> set[str]:
    watchlist = await db.fetch_watchlist_tickers(user_id="default")
    positions = await db.fetch_position_tickers(user_id="default")
    return set(watchlist) | set(positions)
```

The market-data source itself (`source.get_tickers()`) is kept in sync with this same union by the API layer calling `source.add_ticker(...)` / `source.remove_ticker(...)` whenever a watchlist entry or a position is created/closed — e.g., a `POST /api/watchlist` handler calls `await source.add_ticker(ticker)` right after the DB insert, and `POST /api/portfolio/trade` calls it too when a buy opens a new position outside the current watchlist. `app/market/` never queries the database directly; it only reacts to `add_ticker`/`remove_ticker` calls made by the routes that own that decision. This keeps the market package's only responsibility "track whatever set of tickers I'm told to track," which is what makes it swappable and independently testable.

---

## 10. Price History Endpoint

`backend/app/market/prices_route.py` — thin route, all logic lives in `PriceHistoryBuffer`.

```python
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/prices", tags=["prices"])

def create_history_router(history: PriceHistoryBuffer) -> APIRouter:
    @router.get("/{ticker}/history")
    async def get_price_history(ticker: str) -> dict:
        points = history.get(ticker.upper())
        if not points:
            raise HTTPException(status_code=404, detail=f"No history for {ticker}")
        return {"ticker": ticker.upper(), "points": points}
    return router
```

Used by the frontend to seed the main chart on ticker selection (PLAN.md §6/§10, Decision #3): fetch history once on click, render it, then append live points as SSE events arrive for that ticker — no polling needed after the initial load.

---

## 11. Wiring It All Together at Startup

`backend/app/main.py` (illustrative)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.market import (
    PriceCache, PriceHistoryBuffer, MarketSinks,
    create_market_data_source, create_stream_router, create_history_router,
)

DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]

price_cache = PriceCache()
price_history = PriceHistoryBuffer()
sinks = MarketSinks(price_cache, price_history)
market_source = create_market_data_source(sinks)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tickers = await load_watchlist_and_position_tickers()  # from SQLite, union per §9.1
    await market_source.start(tickers or DEFAULT_TICKERS)
    yield
    await market_source.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(price_cache))
app.include_router(create_history_router(price_history))
```

`market_source` and the two sinks are created at module scope (not inside `lifespan`) so route handlers elsewhere in the app (watchlist, trade execution) can import and call `market_source.add_ticker(...)` / `price_cache.get_price(...)` without needing FastAPI dependency injection plumbing threaded through every layer.

---

## 12. Testing Strategy

Already implemented (`backend/tests/market/`):

| Area | What's verified |
|---|---|
| `PriceUpdate` | `change`, `change_percent`, `direction`, `to_dict()` for up/down/flat/zero-previous-price cases |
| `PriceCache` | thread-safety under concurrent updates, `version` monotonicity, `get`/`get_all`/`remove` correctness |
| `GBMSimulator` | prices stay positive, Cholesky matrix is valid (PSD) for 1/2/n tickers, dynamic add/remove rebuilds correlation, event probability fires within expected bounds over many trials |
| `SimulatorDataSource` | `start()` seeds the cache synchronously, prices change over time, `stop()` is idempotent, `add_ticker`/`remove_ticker` take effect |
| `create_market_data_source` | env var present/absent/empty-string selects the right class |
| `MassiveDataSource` | snapshot parsing (happy path + malformed snapshot skip-and-continue), 401/429/network failures don't kill the poll loop, thread offload for the sync client |

Added for the pieces specified in this document (127 tests pass in total):

- **`PriceHistoryBuffer`**: append respects `maxlen` (oldest points evicted first), `get()` on an unknown ticker returns `[]` not an error, thread-safety under concurrent `append`/`get`.
- **`MarketSinks`**: one `record()` call updates both the cache and the history buffer consistently (same price, same timestamp) — regression test against the two sinks drifting.
- **`day_open` / `change_pct`**: simulator's day-open equals the seed price for the life of the process; Massive's day-open comes from `prev_day.close` when available and falls back to first-seen price otherwise.
- **History endpoint**: 404 for a ticker with no data yet; ordering is oldest-first; point count never exceeds `MAX_POINTS`.
- **SSE ∪ filtering**: a route-layer test that a position-only ticker (removed from watchlist) still appears in the SSE payload, and a plain watchlist ticker with no position also appears.

E2E coverage (`test/`, Playwright, per PLAN.md §12) exercises the whole chain: fresh start shows streaming prices, add/remove watchlist ticker updates the SSE set without reconnect, buy/sell updates portfolio-visible tickers, and SSE reconnection after a simulated disconnect.

---

## 13. Design Decisions Log (this document)

| # | Decision | Rationale |
|---|---|---|
| 1 | Keep `MarketDataSource` as an ABC, not a `Protocol` | Both implementations are stateful with an explicit `start`/`stop` lifecycle; nominal typing plus `abstractmethod` catches a missing method at class-definition time |
| 2 | `PriceCache` uses `threading.Lock`, not `asyncio.Lock` | Writers run on the event loop; readers may run from sync code paths (e.g. trade validation); critical sections are microsecond dict ops, so a blocking lock never meaningfully stalls the loop |
| 3 | `PriceHistoryBuffer` is a separate object from `PriceCache`, unified by `MarketSinks` | Keeps "latest value" and "recent series" as separately-testable, separately-scoped concerns while guaranteeing they're written together, not simulating one from the other |
| 4 | `day_open` lives in `PriceCache`, set once via `set_day_open` / `setdefault` | Must survive for the life of the process regardless of how many ticks occur; `setdefault` semantics make "first price wins" trivial and idempotent across repeated calls |
| 5 | Massive's day-open prefers `prev_day.close`, falls back to first-seen price | Matches what a real trading terminal calls "today's change %"; the fallback keeps the code correct even if that field is momentarily unavailable from the API |
| 6 | Watchlist ∪ positions filtering lives in the API/routes layer, not in `app/market/` | The market package's only job is "track the tickers I'm told to"; DB-aware set-union logic belongs where the DB is already being queried, keeping `app/market/` swappable and dependency-free |
| 7 | SSE skips serialization/send when `PriceCache.version` hasn't changed | Massive polls far slower than the 500ms SSE loop; without the version check the endpoint would re-send identical payloads on every tick between polls |
