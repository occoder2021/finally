# FinAlly E2E suite

Playwright, run from the host against the composed app (PLAN.md §13 S3 /
TEAM_CONTRACT.md §10) — not from a containerized runner.

## Running

```bash
cd test
npm install
npm run install:browsers   # once, downloads the Chromium binary
npm test                   # wipes + rebuilds the isolated e2e stack, waits for /api/health, runs specs
```

`playwright.config.ts`'s `webServer` runs, against its own compose project:

```
docker compose -p finally-e2e down -v && docker compose -p finally-e2e up --build
```

This is a **separate compose project, port, and named volume** from a developer's default
`finally` stack — see the file header of `playwright.config.ts` for exactly which env vars
(`FINALLY_PORT`, `FINALLY_VOLUME`, `LLM_MOCK`) make that isolation real, and "Test isolation"
below for why the `down -v` is safe. Every run therefore starts from a fresh, freshly-seeded
database — that's what lets `00-fresh-start.spec.ts` assert the literal $10,000 seed exactly.

Set `E2E_REUSE=true` to skip the wipe/rebuild and reuse an already-running e2e stack for
faster local iteration; the exact-$10,000 test self-skips in that mode, since freshness is no
longer guaranteed. Override the target port with `PORT` / `BASE_URL`.

Useful variants: `npm run test:headed`, `npm run test:ui`, `npm run test:debug`, `npm run report`.

## Suite layout

Spec files are numbered (`00-`, `10-`, …) because they run in filesystem-sorted order under
`workers: 1` / `fullyParallel: false`, and `00-fresh-start` must run before anything else
mutates state (see "Test isolation").

- `playwright.config.ts` — single worker, Chromium only, isolated compose project
  (`finally-e2e`, port 8001, volume `finally-e2e-data`), `LLM_MOCK=true` forced via
  `webServer.env`, traces/screenshots/video kept on failure.
- `fixtures/money.ts` — currency/percent text parsing (`parseMoney`, `parsePercent`,
  `looksNumeric`) since the contract doesn't pin down exact formatting.
- `fixtures/sse.ts` — connection-status polling, price-change/price-present waits, and a
  network-drop helper for the reconnection scenario.
- `fixtures/reset.ts` — within-run isolation helpers (see "Test isolation" below): default
  watchlist constant, per-spec scratch tickers, portfolio/watchlist getters, best-effort
  cleanup (`closePositionIfAny`, `removeFromWatchlistIfPresent`, `scratchTickerCleanup`).
- `tests/00-fresh-start.spec.ts` — default watchlist, connection dot, streaming prices, and
  the exact $10,000 cash/total-value/no-positions assertion (relies on running first, against
  a freshly-wiped DB).
- `tests/10-watchlist.spec.ts` — add/remove via the UI; duplicate/malformed ticker surfaces a
  readable message in `watchlist-error`.
- `tests/20-trading.spec.ts` — buy, full-close sell (row removed, not left at qty 0),
  oversell rejection, non-positive quantity rejection.
- `tests/30-visualizations.spec.ts` — heatmap, P&L chart, main chart, positions table all
  render non-empty once a position exists.
- `tests/40-chat.spec.ts` — mocked AI chat: successful trade action, a trade that fails
  validation rendering as `failed` regardless of the model's prose, history surviving reload.
- `tests/50-sse-resilience.spec.ts` — drop/restore network, connection dot cycles and
  recovers, stream resumes pushing updates.
- `tests/60-invariants.spec.ts` — session-vs-daily labelling, no-literal-$0 on a fresh ticker,
  a failed AI trade never becomes a position, no float-noise in rendered money; an opt-in
  (`RUN_RESTART_TEST=true`) container-restart persistence test.

## Test isolation

The backend is single-user (PLAN.md §7: every table has `user_id` hardcoded to `"default"`)
and there is no in-product reset endpoint — the orchestrator deliberately rejected adding one
(it would be permanent mutable API surface not in PLAN.md just for test benefit). Isolation
instead comes from two layers:

1. **Cross-run:** every `npm test` invocation wipes and rebuilds its own compose project
   (`finally-e2e`), on its own port, backed by its own named volume (`finally-e2e-data`) —
   never the default project's `finally-data`, which PLAN.md commits to as the literal name
   users are told to `docker volume rm` to reset their real portfolio. That separation is
   what makes `down -v` safe to run unconditionally; see `playwright.config.ts`'s header
   comment for the exact env vars (`FINALLY_PORT`, `FINALLY_VOLUME`) that make it real rather
   than just a `-p` flag (a bare `-p` alone would **not** have been enough — see git history
   on this file/config for the hardcoded-name issue that was caught and fixed before this was
   wired in). **Phase 2 checklist, before the first real run:** confirm
   `docker compose -p finally-e2e down -v` only ever removes `finally-e2e-data`, and that
   `docker volume ls` still shows the real `finally-data` intact afterward.
2. **Within a run:** `00-fresh-start.spec.ts` runs first against the guaranteed-clean DB and
   asserts exact totals; every spec after it mutates state, so they touch only a dedicated
   scratch ticker outside the default 10 (`fixtures/reset.ts` -> `SCRATCH_TICKERS`, never a
   default ticker's position), assert **deltas** rather than absolute totals, and clean up in
   `afterEach` best-effort (a cleanup failure doesn't fail the test, since a prior failure may
   have already left things unexpected).

## Contract gaps noticed while writing specs

- **No testid for the "Session" column label.** `60-invariants.spec.ts` checks the watchlist
  container's text content for the word "session" (not "daily") since there's no selector
  for the label itself, only for value cells. This is a content assertion inside an
  already-identified container, not a new interactive selector, so it doesn't violate the
  "only use §8 testids" rule, but a `watchlist-change-label` testid would make it more
  precise if the column header text ever gets restructured. Not raised as blocking.

## Phase status

**Phase 1 (scaffolding) — done.** All spec files are syntactically valid TypeScript
(`tsc --noEmit` clean) and `playwright test --list` resolves all of them; none have been
executed yet — `frontend/`, `backend/app/api/`, `backend/app/llm/` don't exist yet at time of
writing. The compose isolation (`FINALLY_PORT`/`FINALLY_VOLUME`/`LLM_MOCK`) is confirmed
landed in `docker-compose.yml` and wired into `playwright.config.ts`.

**Phase 2 (execution)** happens once the orchestrator confirms the composed stack is up: run
the Phase 2 checklist above once, then `npm test`, triage every failure against
TEAM_CONTRACT.md, and report each one with the failing testid/endpoint, expected vs. actual,
a minimal repro, and the owning agent.
