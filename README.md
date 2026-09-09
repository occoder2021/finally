# FinAlly — AI Trading Workstation

An AI-powered trading workstation that streams live market data, simulates portfolio trading, and puts an LLM copilot next to the tape — one that can read your positions and place trades from plain English.

Built entirely by coding agents as the capstone for an agentic AI coding course. The full specification lives in [`planning/PLAN.md`](planning/PLAN.md), which is the shared contract every agent works against.

## Status

The project is **under construction**. Only the market data subsystem is built today.

| Component | State |
|---|---|
| Market data (simulator, Massive client, price cache, SSE) | ✅ Built and tested |
| Database, portfolio & trade execution | 🚧 Planned |
| LLM chat integration | 🚧 Planned |
| Next.js frontend | 🚧 Planned |
| Docker image & start/stop scripts | 🚧 Planned |
| Playwright E2E suite | 🚧 Planned |

Anything below marked 🚧 describes the target design, not shipped code.

## What It Will Be

- **Live price streaming** over SSE, with green/red flash animations on every tick
- **Simulated portfolio** — $10k of virtual cash, market orders, instant fills, no fees
- **Portfolio visualizations** — treemap heatmap, P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests trades, and executes them on request
- **Watchlist management** — add and remove tickers by hand or through the assistant
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense, desktop-first

## Architecture

One Docker container serving everything on port 8000:

- **Frontend** — Next.js static export (TypeScript, Tailwind CSS), served by FastAPI 🚧
- **Backend** — FastAPI on Python 3.12, managed with `uv`
- **Database** — SQLite, lazily initialized and seeded on first request 🚧
- **AI** — LiteLLM → OpenRouter (`openai/gpt-oss-120b` on Cerebras) with structured outputs 🚧
- **Market data** — built-in GBM simulator by default, Massive (Polygon.io) API when a key is present

## Running What Exists

The market data subsystem runs standalone. From `backend/`:

```bash
uv sync --dev

# Rich terminal demo of the live price feed
uv run python market_data_demo.py

# Test suite
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .
```

See [`backend/README.md`](backend/README.md) for the module-by-module breakdown.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | For chat | OpenRouter key. Without it the app still runs; `/api/chat` returns a readable "chat unavailable" error. |
| `MASSIVE_API_KEY` | No | Massive (Polygon.io) key for real quotes. Omit to use the simulator — the intended demo path. |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses in tests. Never entered implicitly. |

## Project Structure

```
finally/
├── backend/     # FastAPI uv project — market data subsystem lives here
│   ├── app/market/   # simulator, Massive client, price cache, SSE stream
│   └── tests/        # pytest suite
├── planning/    # PLAN.md — the specification all agents build against
├── .github/     # Claude Code review workflows
├── frontend/    # Next.js static export                        (not yet created)
├── test/        # Playwright E2E tests                          (not yet created)
└── scripts/     # Docker start/stop helpers                     (not yet created)
```

## Planned Quick Start

Once the Docker image exists:

```bash
cp .env.example .env          # add your OPENROUTER_API_KEY
docker build -t finally .
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
# open http://localhost:8000
```

The SQLite database persists in the named volume `finally-data`, so restarting the container keeps your portfolio; only removing the volume resets it.

## License

See [LICENSE](LICENSE).
