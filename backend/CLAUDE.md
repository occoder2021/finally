# Backend — Developer Guide

## Project Setup

```bash
cd backend
uv sync --extra dev   # Install all dependencies including test/lint tools
```

> On a network with a TLS-intercepting proxy, add `--system-certs` to `uv` commands
> (e.g. `uv sync --extra dev --system-certs`) so uv trusts the OS certificate store.

## Market Data API

The market data subsystem lives in `app/market/`. Use these imports:

```python
from app.market import (
    PriceCache, PriceHistoryBuffer, MarketSinks, PriceUpdate,
    MarketDataSource, create_market_data_source,
    create_stream_router, create_history_router,
)
```

`planning/MARKET_DATA_DESIGN.md` is the contract for this subsystem.

### Core Types

- **`PriceUpdate`** — Immutable dataclass: `ticker`, `price`, `previous_price`,
  `day_open`, `timestamp`, plus properties `change`, `change_percent`
  (tick-over-tick), `day_change_percent` (vs. the session-open reference),
  `direction` ("up"/"down"/"flat"), and `to_dict()`.

  `to_dict()` emits exactly the PLAN.md §6 wire contract:
  `ticker, price, prev_price, day_open, change_pct, timestamp, direction`.
  Note `change_pct` is the **session** change vs. `day_open` — never the
  previous-tick change, which must not be presented as daily performance.

- **`PriceCache`** — Thread-safe latest-price store. Key methods:
  - `update(ticker, price, timestamp=None) -> PriceUpdate`
  - `set_day_open(ticker, price)` / `get_day_open(ticker) -> float | None`
    — first write wins, so the reference survives the whole process
  - `get(ticker)`, `get_price(ticker)`, `get_all()`, `remove(ticker)`
  - `version` property — monotonic counter, bumped on every update (SSE change detection)

- **`PriceHistoryBuffer`** — Bounded per-ticker ring buffer (default 200 points)
  feeding the chart-seeding endpoint. `append()`, `get(ticker)` (oldest first,
  `[]` for unknown tickers), `remove(ticker)`.

- **`MarketSinks`** — Bundles the cache and the history buffer so a data source
  writes to both with one `record(ticker, price, timestamp=None)` call, sharing
  one timestamp and one rounded price. Use `sinks.remove(ticker)` to drop a
  ticker from both. Data sources take a `MarketSinks`, never a bare `PriceCache`.

- **`MarketDataSource`** — Abstract interface implemented by `SimulatorDataSource`
  and `MassiveDataSource`. Lifecycle: `start(tickers)` -> `add_ticker()` /
  `remove_ticker()` -> `stop()`.

- **`create_market_data_source(sinks)`** — Factory. Returns `MassiveDataSource`
  if `MASSIVE_API_KEY` is set and non-empty, otherwise `SimulatorDataSource`.

### Day-open reference

`day_open` is the baseline for the session change % shown in the watchlist:

- **Simulator** — the ticker's seed price from `seed_prices.py`, fixed for the
  life of the process.
- **Massive** — the previous trading day's close (`prev_day.close`), falling
  back to the first price seen when that field is unavailable.

### Endpoints

```python
app.include_router(create_stream_router(price_cache))    # GET /api/stream/prices
app.include_router(create_history_router(price_history)) # GET /api/prices/{ticker}/history
```

- **`GET /api/stream/prices`** — SSE (`text/event-stream`). Opens with
  `retry: 1000`, then pushes the **full cache snapshot immediately on connect**
  (including reconnects) and again whenever `PriceCache.version` changes, so an
  idle cache never re-sends an identical payload. Each frame is
  `data: {"AAPL": {...}, ...}` with values shaped per `PriceUpdate.to_dict()`.
- **`GET /api/prices/{ticker}/history`** — Returns `{"ticker", "points"}` with
  points oldest-first; `404` when a ticker has no recorded points yet. The
  frontend fetches this once on ticker selection, then appends live SSE points.

### Application wiring

`app/main.py` builds the cache, history buffer, sinks and data source at module
scope, so route handlers elsewhere can call `market_source.add_ticker(...)` or
`price_cache.get_price(...)` without dependency-injection plumbing. The lifespan
handler starts the feed on boot and stops it on shutdown.

```bash
uv run --system-certs uvicorn app.main:app --port 8000
```

**Tracked ticker set.** Tracking must cover the union of watchlist tickers and
tickers with an open position, so a held ticker dropped from the watchlist keeps
its price. That union is owned by the routes layer (the only part that queries
the database), which keeps the source in sync via `add_ticker`/`remove_ticker`.
`app/market/` never touches the database — it tracks whatever set it is told to.
Until the database layer exists, `app.main.initial_tickers()` returns the default
watchlist and is the single call site to replace.

### Seed Data

Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX. Seed
prices and per-ticker volatility/drift params are in `app/market/seed_prices.py`.

## Running Tests

```bash
uv run --system-certs pytest -q                     # All tests
uv run --system-certs pytest --cov=app              # With coverage
uv run --system-certs ruff check app/ tests/        # Lint
```

## Demo

```bash
uv run --system-certs market_data_demo.py   # Live terminal dashboard with simulated prices
```
