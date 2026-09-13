import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * FinAlly E2E suite.
 *
 * Run from the host (not a containerized runner) against the app started by the root
 * `docker-compose.yml`, per PLAN.md S3 / TEAM_CONTRACT.md §10. Playwright's own `webServer`
 * option brings the stack up and waits for `/api/health`, so `npx playwright test` from this
 * directory is a single command.
 *
 * ISOLATION: the suite runs under its own compose project name (`-p finally-e2e`), its own
 * host port, and its own named volume — distinct from a developer's default `finally`
 * project/port/`finally-data` volume, per the orchestrator's decision. Confirmed available in
 * `docker-compose.yml`:
 *   - `ports: "${FINALLY_PORT:-8000}:8000"` — set `FINALLY_PORT` to avoid colliding with a
 *     dev container on 8000.
 *   - `volumes.finally-data.name: "${FINALLY_VOLUME:-finally-data}"` — set `FINALLY_VOLUME`
 *     to a distinct name (`finally-e2e-data`) so `down -v` below can only ever destroy the
 *     e2e volume, never the default project's real portfolio data (which stays the literal
 *     `finally-data`, as PLAN.md commits to for `docker volume rm finally-data`).
 *   - `environment: LLM_MOCK: ${LLM_MOCK:-false}` — an explicit override so this wins over
 *     `.env`, forced to `true` here so chat is deterministic.
 * `OPENROUTER_API_KEY`/`MASSIVE_API_KEY` stay `env_file`-only and are never touched here.
 *
 * `down -v` before `up` guarantees every run starts from a fresh, freshly-seeded database —
 * this is what lets `00-fresh-start.spec.ts` assert the literal $10,000 seed unconditionally.
 * That only holds when the command actually runs, so `reuseExistingServer` defaults to
 * *false* here (opposite of the Playwright default) — set `E2E_REUSE=true` to skip the
 * wipe/rebuild and reuse an already-running e2e stack for faster local iteration; the
 * exact-$10,000 test self-skips when that flag is set, since freshness is no longer
 * guaranteed. Verify in Phase 2 (before the first real run) that `down -v` only ever removes
 * `finally-e2e-data` and that `finally-data` is untouched — see test/README.md.
 *
 * Tests run with a single worker: the backend is single-user with no reset endpoint, so
 * concurrent specs would race on shared cash/positions/watchlist state. See test/README.md
 * and test/fixtures/reset.ts for how specs keep themselves independent within a run.
 */

const COMPOSE_PROJECT = "finally-e2e";
const COMPOSE_VOLUME = "finally-e2e-data";
const PORT = process.env.PORT ? Number(process.env.PORT) : 8001;
const BASE_URL = process.env.BASE_URL ?? `http://localhost:${PORT}`;
const REPO_ROOT = path.resolve(__dirname, "..");

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["list"], ["html", { open: "never" }]]
    : [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // `down -v` first guarantees a fresh, freshly-seeded database every run. This is only
    // safe because FINALLY_VOLUME is guaranteed set for BOTH `down` and `up`:
    //  - it's one `command` string, so Playwright spawns exactly one child shell process for
    //    the whole "down -v && up --build" chain, and `env` below applies to that one process
    //    (both subcommands inherit the same environment — there is no separate invocation
    //    that could run without it);
    //  - COMPOSE_VOLUME is a hardcoded literal constant, not `process.env.FINALLY_VOLUME ??
    //    ...` — there is no code path where this key is omitted or undefined, so `down -v`
    //    can never silently fall through to the compose file's `${FINALLY_VOLUME:-finally-data}`
    //    default and touch the real volume.
    command: `docker compose -p ${COMPOSE_PROJECT} down -v && docker compose -p ${COMPOSE_PROJECT} up --build`,
    cwd: REPO_ROOT,
    url: `${BASE_URL}/api/health`,
    // Default: always wipe + rebuild, so every run is guaranteed fresh (see file header).
    // Must be false by default (Playwright's own default is true) — true here would let a
    // leftover e2e container from a prior run get reused, skipping `down -v` entirely and
    // silently breaking the "fresh every run" guarantee 00-fresh-start.spec.ts relies on.
    // E2E_REUSE=true is the explicit, opt-in exception for faster local iteration.
    reuseExistingServer: process.env.E2E_REUSE === "true",
    timeout: 180_000,
    env: {
      LLM_MOCK: "true",
      FINALLY_PORT: String(PORT),
      FINALLY_VOLUME: COMPOSE_VOLUME,
    },
  },
});
