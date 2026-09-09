# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: LiteLLM → OpenRouter (Cerebras for fast inference), with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1      # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Optional bind-mount target for local inspection
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── docker-compose.yml        # Optional convenience wrapper
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend lazily initializes the database on first request — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is a convenience mount point for local inspection. By default the container uses the **named volume** `finally-data` mounted at `/app/db` (see §11), so the SQLite file lives inside that volume rather than in the repository. Mounting `db/` as a bind mount instead is a supported alternative, not a requirement.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Required: OpenRouter API key for LLM chat functionality
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false
```

### Behavior

- If `MASSIVE_API_KEY` is set and non-empty → backend uses Massive REST API for market data
- If `MASSIVE_API_KEY` is absent or empty → backend uses the built-in market simulator
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- If `OPENROUTER_API_KEY` is absent or empty → the app still starts and everything except chat works. `/api/chat` returns a structured error stating that chat is unavailable, which the chat panel renders as a friendly message. The backend never silently falls back to mock mode; mock mode is entered only by setting `LLM_MOCK=true` explicitly.
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)

---

## 6. Market Data

### Two Implementations, One Interface

Both the simulator and the Massive client implement the same abstract interface. The backend selects which to use based on the environment variable. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Runs as an in-process background task — no external dependencies

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator

### Shared Price Cache

- The **tracked ticker set** is the union of the watchlist and every ticker with a non-zero position. Removing a held ticker from the watchlist does **not** stop price tracking, so portfolio valuation never loses a price.
- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds the latest price, previous price, session-open price, and timestamp for each ticker
- SSE streams read from this cache and push updates to connected clients
- This architecture supports future multi-user scenarios without changes to the data layer

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- **On every connection — including automatic reconnection — the server immediately pushes the full current price cache as a snapshot**, before resuming incremental updates. A client never waits for the next tick to render prices.
- Server pushes price updates for all tickers in the tracked ticker set at a regular cadence (~500ms)
- Each SSE event contains ticker, price, previous price, timestamp, and change direction
- Client handles reconnection automatically (EventSource has built-in retry)

---

## 7. Database

### SQLite with Lazy Initialization

The backend checks for the SQLite database on startup (or first request). If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically

### Concurrency and Precision

The 30-second snapshot task writes while request handlers read and write, so the database layer must produce consistent writes under concurrent access. The specific connection settings are an implementation choice; the required outcome is that a trade's cash, position and trade-log writes commit atomically, and that overlapping requests can never observe a partially applied trade or overspend the cash balance.

One precision policy applies everywhere fractional shares and cash are written or compared. Rounding cash to two decimals on write is not by itself a sufficient accounting policy — the policy must also define the epsilon below which a quantity counts as zero. Fully closed positions are **deleted** rather than left at `quantity = 0`.

### Schema

All tables include a `user_id` column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration.

**users_profile** — User state (cash balance)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance` REAL (default: `10000.0`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost` REAL
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**trades** — Trade history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `price` REAL
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded every 30 seconds by a background task, and immediately after each trade execution.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `total_value` REAL
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — trades executed, watchlist changes made; null for user messages)
- `created_at` TEXT (ISO timestamp)

### Default Seed Data

- One user profile: `id="default"`, `cash_balance=10000.0`
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots for the P&L chart, oldest → newest, capped at the 500 most recent |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |
| GET | `/api/chat/history` | Recent conversation, oldest → newest, capped at the 50 most recent messages, each with its recorded action outcomes |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

### Trade Execution Contract

Manual trades and LLM-initiated trades call the **same** backend execution function, so validation and accounting cannot diverge.

- Reject non-positive and non-finite quantities, insufficient cash on a buy, insufficient shares on a sell, and any ticker with no usable cached price.
- Fill at the cached price **at execution time**. Because the LLM reasons over a snapshot taken before it responds, its fills may differ slightly from the prices it quoted — expected and acceptable in a simulator.
- Update cash, positions and the trade log atomically, with the balance check performed inside the transaction.
- Errors use one envelope, `{"error": {"code": ..., "message": ...}}`, with `400` on validation failure and a message readable enough to show the user verbatim.

### Watchlist Input Rules

- Ticker input is trimmed and upper-cased before the `UNIQUE(user_id, ticker)` check.
- Malformed symbols are rejected. Each market data source documents which symbols it supports; a synthesized simulator price must never be presented as confirmation that a real listing exists.

### Portfolio History Bounds

- `GET /api/portfolio/history` returns at most the 500 most recent snapshots, in chronological order.
- Snapshots older than 30 days are pruned for the local demo. No further filtering or downsampling until a concrete need appears.

---

## 9. LLM Integration

When writing code to make calls to LLMs, use cerebras-inference skill to use LiteLLM via OpenRouter to the `openrouter/openai/gpt-oss-120b` model with Cerebras as the inference provider. Structured Outputs should be used to interpret the results.

There is an OPENROUTER_API_KEY in the .env file in the project root.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads conversation history from the `chat_messages` table, bounded to the **last 20 messages**
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM via LiteLLM → OpenRouter, requesting structured output, using the cerebras-inference skill
5. Parses and **fully validates** the structured JSON response before executing anything — a malformed or schema-invalid response executes **no** actions and returns a readable error
6. Executes the validated trades and watchlist changes sequentially, best-effort: a later action may fail because an earlier one consumed the cash, and each action's actual outcome is recorded
7. Stores the message and the recorded action outcomes in `chat_messages`
8. Returns the complete JSON response to the frontend (no token-by-token streaming — Cerebras inference is fast enough that a loading indicator is sufficient)

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

If a trade fails validation (e.g., insufficient cash), the failure is recorded and returned with the chat response.

The UI reports **what actually happened**, action by action — the model's `message` is never treated as evidence that a trade executed, so a claimed fill that failed validation must render as a failure.

A repair retry or an alternate-provider fallback is out of scope for the first version: if the provider returns output that does not satisfy the schema, report the error.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenRouter. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), **session change %** (versus the ticker's session-open price, labelled as session change — never presented as daily performance, and never derived from the previous tick), and a sparkline mini-chart (accumulated from SSE since page load)
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Market orders, instant fill.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Executed trades and watchlist changes appear inline with their **actual outcome** — succeeded, or failed with the reason. History loads from `GET /api/chat/history` on mount, so a page refresh restores the visible conversation, not just the database rows.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- Canvas-based charting library preferred (Lightweight Charts or Recharts) for performance
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme
- **Division of truth**: the backend is authoritative for cash, quantity and average cost; the client recomputes market values, total value and unrealized P&L from the live SSE prices rather than polling. Holdings are refetched after every manual or AI-initiated action, so the header and the positions table cannot disagree on screen.
- A ticker with no price in the cache renders as **unavailable** — never valued at zero, and never silently dropped from the total

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Docker Volume

The SQLite database persists via a named Docker volume:

```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

`finally-data` is a Docker **named volume** mounted at `/app/db` inside the container, where the backend writes `finally.db`. Docker manages it; it does not live in the repository — the top-level `db/` directory is a placeholder for the alternative bind-mount setup (`-v "$(pwd)/db:/app/db"`), which is supported but not the default. Either way, stopping and restarting the container preserves the portfolio; only removing the volume resets it.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

---

## 13. Plan Review — Questions, Clarifications & Simplifications

*Added by a documentation review pass over §1–12, cross-checked against the completed market data subsystem (`planning/MARKET_DATA_SUMMARY.md`). Items are grouped by how much they block implementation. Each carries a recommended default so an agent can proceed without waiting for an answer — strike the ones you disagree with.*

> **Status: reviewed and resolved.** §14 records which of these items are adopted, and the adopted ones (G1–G5, G7, Q2, Q4, Q6–Q13) are now folded into §1–12 above, which is the implementation contract. Everything else here is explicitly deferred. Read §13 as the reasoning behind those decisions, not as a backlog.

### 13.1 Contradictions & Gaps

**G1 — Docker volume: named volume or bind mount?** §11 shows `docker run -v finally-data:/app/db` (a *named* volume), but the next sentence says "the `db/` directory in the project root maps to `/app/db`", and §4 lists a top-level `db/.gitkeep`. These are mutually exclusive. *Recommendation:* use a bind mount (`-v "$(pwd)/db:/app/db"`) — it matches the documented directory structure, keeps `.gitkeep` meaningful, and makes the SQLite file inspectable on the host, which matters for a teaching project. Then fix the sample command.

**G2 — No endpoint to load chat history.** `chat_messages` is persisted and §10 requires a "scrolling conversation history", but §8 lists only `POST /api/chat`. After a page refresh the panel would render empty despite the data existing. *Recommendation:* add `GET /api/chat/history` returning the last N messages (`role`, `content`, `actions`, `created_at`).

**G3 — Tracked tickers vs. watchlist.** The price cache is fed from "the user's watchlist". If the user (or the LLM) removes a ticker they still hold, that position loses its price and portfolio valuation silently breaks. *Recommendation:* state explicitly that the tracked ticker set is **watchlist ∪ tickers with a non-zero position**, and that removing a held ticker from the watchlist does not stop price tracking.

**G4 — "Daily change %" is undefined for the simulator.** §10 asks the watchlist to show daily change %, but `PriceUpdate` carries only the *previous tick* price and the simulator has no previous close. *Recommendation:* define it as change vs. the ticker's seed price at process start, serve it from the backend, and label it "Session %" rather than implying a real trading day. In Massive mode it can come from the prev-close field.

**G5 — `/api/portfolio/history` takes no parameters and grows unbounded.** A 30-second cadence produces ~2,880 rows/day, forever, in a persisted volume. *Recommendation:* add `?limit=` (default ~500) and `?since=`, and either downsample on read or document a retention rule.

**G6 — Nothing reads the `trades` table.** It is specified as an append-only log but no endpoint or UI element surfaces it. *Recommendation:* either add `GET /api/portfolio/trades` plus a compact "recent fills" list — cheap, and it makes the AI's auto-executed trades auditable — or state that the table is for audit only and is deliberately not surfaced.

**G7 — Behavior when `OPENROUTER_API_KEY` is missing.** §5 marks it "Required", but the app is fully functional without it (market data, trading, portfolio). *Recommendation:* the app must still start; `/api/chat` returns a structured error the panel renders as a friendly message. Do **not** silently fall back to mock mode — a mock reply that looks real is worse than an honest error.

### 13.2 Questions Needing a Decision

**Q1 — SSE payload shape.** Per-ticker events at ~500ms across 10+ tickers means 20+ events/sec and 20+ client state updates/sec. Is one **batched** event per tick (`data: [{ticker, price, ...}, ...]`) acceptable? It is simpler, cheaper to render, and keeps per-tick sparkline appends time-aligned. Also unspecified: the event name(s), whether a `retry:` interval is sent, and whether a `: keepalive` comment is emitted (needed to survive idle proxies).

**Q2 — Initial snapshot on connect.** A client connecting mid-tick sees nothing until the next change is detected — and in Massive mode (15s polling) that is a visibly empty grid. *Recommendation:* push the full cache as a `snapshot` event immediately on connect, then deltas.

**Q3 — Chart history on page load.** §2 accepts sparklines that fill in progressively, but the same constraint leaves the **main chart area empty on load** and wipes it on every refresh — and that is the most visually prominent panel. Should `PriceCache` keep a bounded in-memory ring buffer (e.g. last 600 ticks per ticker, ~5 minutes) exposed via `GET /api/history/{ticker}`? It needs no schema change and fixes both the main chart and post-refresh sparklines.

**Q4 — Unknown or malformed tickers on watchlist add.** What should `POST /api/watchlist {"ticker": "ZZZZ"}` do? The simulator's seed table only knows the 10 defaults. Options: (a) validate against a known-symbol list and reject, or (b) accept anything and synthesize a seed price. Also confirm: is input trimmed and upper-cased before the `UNIQUE(user_id, ticker)` check, and is there a **cap** on watchlist size? A cap matters in Massive mode (free tier = 5 calls/min).

**Q5 — Massive mode materially changes the feel of the app.** At 15s polling, prices flash at most ~4x/min and sparklines gain ~4 points/min, so the signature flashing-terminal effect largely disappears. Is that accepted, or should the plan state plainly that the simulator is the intended demo path and Massive is a correctness/architecture showcase?

**Q6 — Trade validation contract.** Unspecified: rejection of `quantity <= 0` and non-finite values; whether trading a ticker with no cached price is allowed; whether selling a full position **deletes** the row or leaves `quantity = 0` (§2 hedges with "updates or disappears"); and the error response shape shared by all endpoints. *Recommendation:* one envelope `{"error": {"code": ..., "message": ...}}`, `400` on validation failure, delete the row below the zero epsilon.

**Q7 — Float hygiene.** Cash and quantities are `REAL`. Buying then fully selling a position leaves residue like `1e-13` shares or `9999.999999999998` cash, which then renders in the UI. Specify: cash rounded to 2dp on write, quantity treated as zero below a documented epsilon (e.g. `1e-9`).

**Q8 — Does the LLM see fresh prices, and can it trade in dollars?** The prompt is built from a cache snapshot, but execution happens after the model responds, so fills differ slightly from the price the model reasoned about. That is fine in a simulator — but say so, since §12 asks for trade-validation tests. Separately, users *will* ask "buy $2,000 of NVDA" and the schema accepts only share `quantity`. Either state that the model must convert (it has prices and cash in context) or add an optional `notional` field.

**Q9 — Semantics of the `trades` array.** Trades execute in order, so a later one can fail because an earlier one consumed the cash. All-or-nothing, or best-effort? *Recommendation:* best-effort, with each trade's outcome recorded in `actions` and summarized back to the user.

**Q10 — Conversation history budget.** "Recent conversation history" is unquantified. Pick a number (e.g. last 20 messages) so context size is bounded and mock-mode E2E runs stay deterministic.

**Q11 — Structured outputs on this provider.** §9 requires JSON-schema structured output from `openrouter/openai/gpt-oss-120b` via Cerebras. Confirm the provider honors `response_format` with a schema; if it supports only `json_object`, the plan needs a named fallback (schema in the prompt, then validate, then one repair retry). §12 already asks for "graceful handling of malformed responses" — this is the concrete strategy behind it.

**Q12 — SQLite concurrency.** The 30s snapshot task writes while request handlers read and write. Specify WAL mode, `check_same_thread=False`, and a short `busy_timeout`, or the first `database is locked` will surface as a flaky E2E failure.

**Q13 — Who computes the live portfolio value?** §8's `GET /api/portfolio` returns total value and P&L, while §10 requires a header that updates live. Confirm the split: REST is the source of truth for cash, quantity and average cost; the client recomputes market values from SSE prices and does not poll. Otherwise the header and the positions table can disagree on screen.

**Q14 — Static export constraints.** `output: 'export'` disables server components, route handlers, middleware, and default image optimization (`images.unoptimized: true` is required). Also confirm the FastAPI catch-all mounts *after* `/api/*` and serves `index.html` for unknown paths.

### 13.3 Opportunities to Simplify

**S1 — One launch path, not three.** §11 specifies four scripts, an optional `docker-compose.yml`, *and* a raw `docker run` example — so ports, volumes and env config live in three places and will drift. Make `docker-compose.yml` the single source of truth and reduce the scripts to thin wrappers around `docker compose up -d --build` and `docker compose down`. The macOS and Windows scripts then differ only in the line that opens the browser.

**S2 — Drop prices from `GET /api/watchlist`.** Returning "tickers with latest prices" duplicates the SSE stream and guarantees a brief stale-price flash on load. Returning tickers only leaves exactly one source of truth for price. Pairs naturally with Q2's connect-time snapshot.

**S3 — Run Playwright from the host, not from a container.** `docker-compose.test.yml` plus a Playwright container is real infrastructure to maintain. Playwright's own `webServer` config can start the app container and run the tests from the host in one command, and it is far easier for students to debug (headed mode, trace viewer). Keep the containerized runner only if cross-platform CI parity is an explicit goal.

**S4 — One snapshot writer.** Snapshots are written from two places (the 30s task and every trade). A single `record_snapshot()` helper called by both, with a guard against duplicate writes inside the same second, avoids a spiky P&L chart immediately after trades.

**S5 — Store `cash_balance` alongside `total_value` in `portfolio_snapshots`.** One extra column, free to add now, makes the P&L chart decomposable into cash vs. market value later. As specified, that split is unrecoverable after the fact.

**S6 — Do the treemap and the positions table both earn their space?** They present the same six numbers in two forms. Both are in scope as written; worth revisiting only if the layout gets cramped, in which case the treemap is the more distinctive of the two.

### 13.4 Minor Notes

- **M1** — §5 says the backend "reads `.env` from the project root", but inside the container there is no `.env` (vars arrive via `--env-file`). Clarify that dotenv loading is a local-dev convenience and environment variables are authoritative.
- **M2** — There is no market-hours concept: the simulator moves prices 24/7 while Massive returns a flat last trade when markets are closed. One sentence prevents this being reported as a bug.
- **M3** — The header shows total value but no baseline. A "total return vs. $10,000" figure is one subtraction and makes the whole app legible at a glance.
- **M4** — Restarts leave gaps in `portfolio_snapshots`, so the P&L chart draws a straight line across downtime. Acceptable — worth stating.
- **M5** — §2 promises no confirmation dialog for manual trades, so a fat-fingered quantity is unrecoverable. Undo is not needed, but the trade bar should echo the estimated cost or proceeds before the click.
- **M6** — Connection indicator: `EventSource.readyState` maps cleanly onto the three dot colors (`OPEN` green, `CONNECTING` after an error yellow, `CLOSED` red). Worth naming so every agent implements it identically.
- **M7** — `chat_messages` grows without bound and there is no way to clear the conversation. `DELETE /api/chat/history` is trivial and genuinely useful when re-running a demo.

---

## 14. Minimal Product Review of Section 13

Section 13 makes sense as a list of things to consider, but it should not become a mandatory implementation backlog. For this single-user, simulated trading product, adopt only the following essentials. These decisions take precedence over the corresponding recommendations in section 13.

1. **Keep holdings priced and the portfolio consistent (G3, Q2, Q13).** Track the union of watchlist tickers and non-zero positions. Send the current price cache on SSE connection, including reconnection. Use backend cash and holdings with the latest streamed prices for all live portfolio displays; refresh holdings after manual or AI actions. A missing price must show as unavailable, never silently value a holding at zero.

2. **Make every trade correct (Q6, Q7, Q8, Q12).** Manual and AI trades must use the same backend execution function: reject non-positive or non-finite quantities, insufficient cash/shares, and missing or unusable prices. Fill at the cached price at execution time. Update cash, positions, and the trade log atomically, with balance checks inside the transaction so overlapping requests cannot overspend. Define one precision policy for fractional shares and cash, remove fully closed positions, and return readable errors. Rounding cash to two decimals on every write is not by itself a sufficient accounting policy. Choose SQLite connection settings to suit the implementation; the required outcome is consistent writes, not a prescribed collection of flags.

3. **Report what AI actions actually did (G7, Q9, Q10, Q11).** The app must start without an LLM key and explain that chat is unavailable; mock mode stays explicit. Bound model context to the last 20 messages. Validate the complete structured response before executing any actions; malformed output executes nothing and returns a readable error. Execute valid actions sequentially, best-effort, and display each actual success or failure rather than treating the model's proposed message as proof of execution. A repair retry or provider fallback is not required for the first version.

4. **Restore the existing conversation (G2).** Add `GET /api/chat/history` with a bounded response, such as the latest 50 messages in chronological order, including recorded action outcomes. Persistence should survive a page refresh in the visible product as well as in the database.

5. **Keep market information honest (G4, Q4).** Normalize ticker input and reject malformed symbols. Define which symbols each source supports; synthetic prices must not imply that a real listing was verified. Omit daily change until a meaningful baseline is available, or label simulator change explicitly as session change. Do not present previous-tick change as daily performance.

6. **Bound portfolio history simply (G5).** Return at most 500 recent snapshots in chronological order and retain the latest 30 days for the local demo. Skip additional filtering and downsampling until needed.

7. **Resolve the launch contradiction with the smallest edit (G1).** Keep the named volume already shown in the Docker command and correct the sentence claiming it maps to the repository's `db/` folder. A bind mount is an alternative, not a requirement. Confirm that restarting the container preserves the portfolio.

**Defer the rest.** Chart-history storage, a recent-fills panel, dollar-denominated order fields, extra snapshot columns, chat deletion, and launch/test infrastructure rewrites are not necessary to deliver the existing experience. Keep progressive charts, the current SSE contract, and the planned test runner unless implementation reveals a concrete problem. Do not suppress legitimate post-trade snapshots merely because two trades occur within one second (S4). Retain the positions table as the precise holdings view; the treemap is the first visualization to defer if the interface feels crowded (S6).
