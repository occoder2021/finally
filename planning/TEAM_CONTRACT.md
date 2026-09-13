# FinAlly — Team Contract

**Status: binding.** This file is the interface agreement between the six agents building
FinAlly in parallel in one shared working tree. `PLAN.md` is *what* to build and always
wins on product behaviour; this file is *who builds which file* and *what the seams look
like*, so two agents never guess the same boundary differently.

If you believe something here is wrong, do **not** silently deviate — report it to the
orchestrator (the lead) and keep going on everything else.

---

## 1. Team & file ownership

You may create and edit **only** files under the paths you own. Reading anything is always
fine and encouraged. If you need a change in someone else's file, message the orchestrator.

| Agent | Owns (exclusive write access) |
|---|---|
| **db-engineer** | `backend/app/db/**`, `backend/tests/db/**` |
| **backend-api** | `backend/app/api/**`, `backend/app/main.py`, `backend/tests/api/**`, `backend/pyproject.toml` |
| **llm-engineer** | `backend/app/llm/**`, `backend/tests/llm/**` |
| **frontend** | `frontend/**` |
| **devops** | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `scripts/**`, `.env.example`, `db/.gitkeep`, `.gitignore` |
| **integration-tester** | `test/**` |

Nobody edits `backend/app/market/**` — the market data subsystem is complete and is a
fixed dependency. Nobody edits `planning/**` except the orchestrator. `backend/pyproject.toml`
is owned by **backend-api**: if you need a dependency added (e.g. `litellm`), ask the
orchestrator rather than editing it yourself, to avoid two agents racing on `uv.lock`.

**Shared-tree discipline.** All six of you work in the same checkout at
`C:\Users\ocana\cursor_proj2\finally` on branch `agent-teams`. Do not run `git commit`,
`git checkout`, `git stash`, `git restore`, or any other branch- or index-level git
command — the orchestrator handles all committing. `git status` / `git diff` are fine.

---

## 2. Existing foundation (do not rebuild)

`backend/app/market/` is finished and documented in `backend/CLAUDE.md` and
`planning/MARKET_DATA_DESIGN.md`. Public API:

```python
from app.market import (
    PriceCache, PriceHistoryBuffer, MarketSinks, PriceUpdate,
    MarketDataSource, create_market_data_source,
    create_stream_router, create_history_router,
)
```

Already wired in `backend/app/main.py` at module scope: `price_cache`, `price_history`,
`sinks`, `market_source`. Already-live endpoints:

- `GET /api/stream/prices` — SSE, full snapshot on connect, frame shape
  `data: {"AAPL": {ticker, price, prev_price, day_open, change_pct, timestamp, direction}, ...}`
  where `change_pct` is **session** change vs. `day_open` (never tick-over-tick).
- `GET /api/prices/{ticker}/history` — `{"ticker", "points":[{timestamp, price}, ...]}`, 404 when empty.
- `GET /api/health`.

Read prices with `price_cache.get_price(ticker) -> float | None`. A `None` price means
**unavailable** — never substitute `0`.

---

## 3. Precision policy (single source of truth)

Applies everywhere money or shares are written or compared. Lives in `backend/app/db/money.py`,
owned by **db-engineer**, imported by everyone who needs it.

```python
QTY_EPSILON = 1e-9          # |quantity| < QTY_EPSILON  =>  the position is closed
CASH_DP     = 2             # cash is rounded to 2dp on every write
QTY_DP      = 8             # quantity is rounded to 8dp on every write

def round_cash(x: float) -> float: ...      # round(x, CASH_DP)
def round_qty(x: float) -> float: ...       # round(x, QTY_DP)
def is_zero_qty(x: float) -> bool: ...      # abs(x) < QTY_EPSILON
```

A fully closed position is **DELETEd**, never left at `quantity = 0`. A buy's cost must be
checked against cash *inside* the transaction, using `round_cash`, and a buy is allowed when
`cost <= cash_balance + 1e-9` (so exact-full-spend does not fail on float noise).

---

## 4. Error envelope (all endpoints)

Every 4xx/5xx from `/api/*` returns exactly:

```json
{"error": {"code": "INSUFFICIENT_CASH", "message": "Need $1,900.00 but only $1,000.00 available."}}
```

`message` is shown to the user verbatim, so write it in plain English with concrete numbers.
Validation failures are `400`. Codes in use (extend if needed, keep SCREAMING_SNAKE):

`INVALID_QUANTITY`, `INVALID_SIDE`, `INVALID_TICKER`, `INSUFFICIENT_CASH`, `INSUFFICIENT_SHARES`,
`PRICE_UNAVAILABLE`, `TICKER_NOT_FOUND`, `DUPLICATE_TICKER`, `WATCHLIST_FULL`, `NOT_FOUND`,
`CHAT_UNAVAILABLE`, `LLM_INVALID_RESPONSE`, `LLM_ERROR`.

**Documented exception:** `GET /api/prices/{ticker}/history` lives in the frozen market
module and 404s with a bare FastAPI `{"detail": ...}` body rather than this envelope. The
frontend treats that 404 as "no history yet" for a newly-added ticker. Do not "fix" the
market module for this; do not assert the envelope shape against that one endpoint.

**backend-api** installs one FastAPI exception handler that turns a shared
`ApiError(code, message, status=400)` exception into that envelope; `ApiError` is defined in
`backend/app/db/errors.py` (db-engineer) so the db and llm layers can raise it without
importing the api layer.

---

## 5. Database layer — `backend/app/db/` (db-engineer)

SQLite file path from env `FINALLY_DB_PATH`, default `db/finally.db` relative to the backend
working directory; the container sets it to `/app/db/finally.db`. Lazy init: on first use,
create tables and seed if missing. Schema exactly as `PLAN.md` §7 (six tables, every table
has `user_id TEXT DEFAULT 'default'`). Seed: profile with `cash_balance = 10000.0`, and the
ten default tickers AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX.

Concurrency: the 30s snapshot task writes while request handlers read/write. Required
outcome — a trade's cash + position + trade-log writes commit atomically, and overlapping
requests can never observe a partial trade or overspend cash. (WAL, `check_same_thread=False`
and a `busy_timeout` are the obvious way there, but the settings are your call.)

### Public API — other agents import exactly these

```python
from app.db import (
    init_db, get_connection, reset_db_for_tests,
    ApiError,
    round_cash, round_qty, is_zero_qty,
    # profile / portfolio
    get_cash_balance, get_positions, get_position,
    # trading — THE single execution path, used by manual AND LLM trades
    execute_trade,
    # watchlist
    get_watchlist, add_to_watchlist, remove_from_watchlist,
    # tracked set
    get_tracked_tickers,
    # history
    record_snapshot, get_snapshots, prune_snapshots,
    # chat
    get_chat_messages, append_chat_message,
)
```

Signatures (keyword-friendly; all take `user_id: str = "default"` as the last parameter):

```python
def init_db() -> None                                  # idempotent; creates + seeds
def get_cash_balance(user_id="default") -> float
def get_positions(user_id="default") -> list[Position]  # Position: ticker, quantity, avg_cost
def get_position(ticker, user_id="default") -> Position | None

def execute_trade(ticker: str, side: str, quantity: float,
                  price: float, user_id="default") -> TradeResult
# TradeResult (dataclass): ticker, side, quantity, price, total, cash_after, trade_id, executed_at
# Raises ApiError on: non-positive/non-finite quantity (INVALID_QUANTITY),
# insufficient cash (INSUFFICIENT_CASH), insufficient shares (INSUFFICIENT_SHARES).
# `price` is supplied by the caller, which has already resolved it from the price cache and
# raised PRICE_UNAVAILABLE if it was None. execute_trade never imports app.market.

def get_watchlist(user_id="default") -> list[str]       # upper-cased, insertion order
def add_to_watchlist(ticker, user_id="default") -> str  # returns normalized ticker;
                                                        # raises DUPLICATE_TICKER / INVALID_TICKER
def remove_from_watchlist(ticker, user_id="default") -> None   # raises TICKER_NOT_FOUND
def get_tracked_tickers(user_id="default") -> list[str] # watchlist UNION non-zero positions

def record_snapshot(total_value: float, user_id="default") -> None
def get_snapshots(limit=500, user_id="default") -> list[dict]   # chronological, {total_value, recorded_at}
def prune_snapshots(days=30, user_id="default") -> int

def get_chat_messages(limit=50, user_id="default") -> list[ChatMessage]  # chronological
# ChatMessage: id, role, content, actions (parsed list[dict] | None), created_at
def append_chat_message(role: str, content: str, actions: list[dict] | None = None,
                        user_id="default") -> ChatMessage
```

**Ticker normalization** (db-engineer owns the one implementation, `normalize_ticker`):
trim, upper-case, then require `^[A-Z]{1,5}$` — otherwise `INVALID_TICKER` with message
"'{input}' is not a valid ticker symbol." Normalization happens *before* the
`UNIQUE(user_id, ticker)` check. Watchlist cap: **25** tickers (`WATCHLIST_FULL`).

---

## 6. Backend API — `backend/app/api/` (backend-api)

Owns routers, wiring in `main.py`, the exception handler, the snapshot background task, and
keeping the market source's tracked set in sync.

### Endpoints

**`GET /api/portfolio`**
```json
{"cash_balance": 8100.00,
 "positions": [{"ticker":"AAPL","quantity":10,"avg_cost":190.00,
                "current_price":191.50,"market_value":1915.00,
                "unrealized_pnl":15.00,"pnl_percent":0.79,"price_available":true}],
 "total_value": 10015.00,
 "total_unrealized_pnl": 15.00,
 "starting_cash": 10000.00}
```
`current_price`/`market_value`/`unrealized_pnl`/`pnl_percent` are `null` and
`price_available` is `false` when the cache has no price. Such a position contributes `0`
to `total_value` but the client must render it as unavailable (see §7).

**`POST /api/portfolio/trade`** — body `{"ticker":"AAPL","quantity":10,"side":"buy"}`.
Resolve price from `price_cache.get_price()`; `None` → `PRICE_UNAVAILABLE`. Then call
`execute_trade`. On success, `record_snapshot(...)` immediately and add the ticker to the
tracked set. Returns:
```json
{"trade": {"ticker":"AAPL","side":"buy","quantity":10,"price":190.00,
           "total":1900.00,"executed_at":"...","cash_after":8100.00}}
```

**`GET /api/portfolio/history`** → `{"snapshots":[{"total_value":10000.0,"recorded_at":"..."}]}`,
chronological, at most 500.

**`GET /api/watchlist`** → `{"tickers":["AAPL","GOOGL",...]}` — **tickers only, no prices**
(prices come from SSE only, so there is exactly one price source and no stale flash on load).

**`POST /api/watchlist`** — body `{"ticker":"pypl"}` → `{"ticker":"PYPL"}` (201). Also calls
`market_source.add_ticker()`.

**`DELETE /api/watchlist/{ticker}`** → 204. Calls `market_source.remove_ticker()` **only if**
the ticker has no open position (`get_tracked_tickers` is the authority).

### Background work
- Snapshot task every 30s: value the portfolio from `price_cache` + db holdings, call
  `record_snapshot`. Do **not** suppress a post-trade snapshot that lands in the same second.
- Prune snapshots older than 30 days on startup.
- On startup, replace `main.initial_tickers()` with `get_tracked_tickers()` after `init_db()`.
- Static file serving: mount the Next.js export from `static/` (env `FINALLY_STATIC_DIR`,
  default `static`) as a catch-all that is registered **after** all `/api/*` routes and
  serves `index.html` for unknown non-API paths. Skip gracefully if the dir is absent.

---

## 7. LLM — `backend/app/llm/` (llm-engineer)

Owns the LiteLLM/OpenRouter/Cerebras call, the structured-output schema, prompt building,
mock mode, and its own router `create_chat_router(...)` which **backend-api** mounts in
`main.py`. Follow the project skill `cerebras-inference`
(`openrouter/openai/gpt-oss-120b`, `extra_body={"provider":{"order":["cerebras"]}}`,
`reasoning_effort="low"`, `response_format=<pydantic model>`).

**`POST /api/chat`** — body `{"message": "..."}` →
```json
{"message": "Bought 5 NVDA at $480.12.",
 "actions": [
   {"type":"trade","status":"success","ticker":"NVDA","side":"buy","quantity":5,
    "price":480.12,"total":2400.60,"detail":"Bought 5 NVDA at $480.12"},
   {"type":"trade","status":"failed","ticker":"TSLA","side":"buy","quantity":100,
    "detail":"Need $24,000.00 but only $1,200.00 available."},
   {"type":"watchlist","status":"success","ticker":"PYPL","action":"add","detail":"Added PYPL"}
 ]}
```

**`GET /api/chat/history`** → `{"messages":[{"role","content","actions","created_at"}]}`,
chronological, at most 50.

Rules (from `PLAN.md` §9 / §14.3):
- No `OPENROUTER_API_KEY` and `LLM_MOCK != "true"` → `/api/chat` returns
  `{"error":{"code":"CHAT_UNAVAILABLE", ...}}` with a friendly message. **Never** fall back
  to mock silently; mock mode is entered only by `LLM_MOCK=true`.
- Context: portfolio (cash, positions with P&L, watchlist with live prices, total value) +
  the last **20** messages from `get_chat_messages`.
- Validate the *complete* structured response before executing *anything*. Malformed →
  execute nothing, return `LLM_INVALID_RESPONSE`. No repair retry, no provider fallback.
- Execute validated actions **sequentially, best-effort**: a later trade may fail because an
  earlier one spent the cash. Record each action's *actual* outcome. The UI reports outcomes,
  never the model's prose, as evidence of execution.
- Trades go through the **same** path as manual trades: resolve price from `price_cache`,
  then `execute_trade`. Never re-implement validation.
- Persist the user message and the assistant message (with `actions`) via `append_chat_message`.
- `LLM_MOCK=true` must be deterministic and must still exercise the real execution path —
  a message containing "buy N TICKER" / "sell N TICKER" produces that trade action; "add
  TICKER to watchlist" produces that watchlist action; anything else is a canned analysis reply.

---

## 8. Frontend — `frontend/` (frontend)

Next.js + TypeScript, `output: 'export'`, `images: {unoptimized: true}`, Tailwind, dark theme.
No server components / route handlers / middleware (static export forbids them). All calls
are same-origin `/api/*`.

Division of truth: backend is authoritative for **cash, quantity, avg_cost**; the client
recomputes market value, total value and unrealized P&L from **live SSE prices**, and does
not poll. Refetch `/api/portfolio` and `/api/watchlist` after every manual or AI action.
A ticker with no cached price renders as `—` / "unavailable", never `$0`, and never
disappears from the positions table.

Panels required: watchlist (price, session change % labelled **session**, sparkline
accumulated from SSE), main chart (seed from `/api/prices/{ticker}/history`, then append SSE
points), portfolio treemap, P&L chart from `/api/portfolio/history`, positions table, trade
bar (echoes estimated cost/proceeds before the click), AI chat panel (loads
`/api/chat/history` on mount, renders each action's actual outcome), header (total value,
total return vs. $10,000, cash, connection dot).

Connection dot from `EventSource.readyState`: `OPEN` → green, `CONNECTING` after an error →
yellow, `CLOSED` → red.

Colors: accent `#ecad0a`, blue `#209dd7`, purple `#753991` (submit buttons), background
`#0d1117`. Price flash: green/red background class applied on change, faded out over ~500ms.

### `data-testid` contract (binding — integration-tester writes against these)

| testid | element |
|---|---|
| `connection-status` | the dot; `data-state` = `connected` \| `connecting` \| `disconnected` |
| `cash-balance` | header cash figure |
| `total-value` | header total portfolio value |
| `total-return` | header return vs. $10,000 |
| `watchlist` | watchlist container |
| `watchlist-row-{TICKER}` | one watchlist row |
| `watchlist-price-{TICKER}` | price cell in that row |
| `watchlist-change-{TICKER}` | session change cell |
| `watchlist-remove-{TICKER}` | remove button |
| `watchlist-add-input` / `watchlist-add-submit` | add-ticker form |
| `watchlist-error` | watchlist add error message — renders the envelope's `message` verbatim |
| `main-chart` | selected-ticker chart container |
| `positions-table` | positions table |
| `position-row-{TICKER}` | one position row |
| `position-qty-{TICKER}` / `position-pnl-{TICKER}` | cells in that row |
| `heatmap` | treemap container |
| `pnl-chart` | portfolio value chart container |
| `trade-ticker` / `trade-quantity` / `trade-estimate` / `trade-buy` / `trade-sell` | trade bar |
| `trade-error` | trade error message |
| `chat-panel` / `chat-input` / `chat-send` / `chat-loading` | chat |
| `chat-message-{index}` | one message bubble, `data-role` = `user` \| `assistant` |
| `chat-action-{index}` | one action line, `data-status` = `success` \| `failed` |

---

## 9. DevOps — root (devops)

Multi-stage `Dockerfile`: Node 20 builds `frontend/` to a static export → Python 3.12-slim
with `uv sync --frozen`, frontend output copied to `/app/static`, `EXPOSE 8000`, uvicorn on
`0.0.0.0:8000`. Env `FINALLY_DB_PATH=/app/db/finally.db`, `FINALLY_STATIC_DIR=/app/static`.

`docker-compose.yml` is the single source of truth for ports/volume/env; the four scripts
(`start_mac.sh`, `stop_mac.sh`, `start_windows.ps1`, `stop_windows.ps1`) are thin idempotent
wrappers over `docker compose up -d --build` / `docker compose down`, differing only in the
browser-open line. Named volume `finally-data` → `/app/db`. `.env.example` with
`OPENROUTER_API_KEY=`, `MASSIVE_API_KEY=`, `LLM_MOCK=false`. `.dockerignore` must exclude
`backend/.venv`, `**/node_modules`, `**/__pycache__`, `.git`, `db/`, `test/`.

Restarting the container must preserve the portfolio; only removing the volume resets it.

---

## 10. Integration testing — `test/` (integration-tester)

Playwright, run from the host against the composed app, `LLM_MOCK=true`. Scenarios from
`PLAN.md` §12: fresh start, watchlist add/remove, buy, sell (including full close),
visualizations render, mocked AI chat with an executed trade shown inline, SSE reconnect.
Use only the `data-testid` values in §8; if you need one that isn't listed, ask the
orchestrator to add it rather than inventing it.

Report every failure back to the owning agent through the orchestrator, with the failing
testid, the expected vs. actual, and a minimal repro.

---

## 11. Definition of done (every agent)

1. Code complete against this contract and `PLAN.md`.
2. Unit tests written and **passing** — backend `cd backend && uv run --system-certs pytest -q`,
   frontend `npm test`. Add `--system-certs` to `uv` commands (TLS-intercepting proxy here).
3. Lint clean: `uv run --system-certs ruff check app/ tests/` (backend) / `npm run lint` (frontend).
4. You did not modify a file you do not own.
5. Report to the orchestrator: what you built, what passes, what's stubbed, and any contract
   friction you hit.
