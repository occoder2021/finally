"""Tests for the SSE price stream contract."""

import json

import pytest

from app.market.cache import PriceCache
from app.market.stream import _generate_events, create_stream_router


class _FakeRequest:
    """Minimal stand-in for a Starlette Request that disconnects on cue."""

    def __init__(self, disconnect_after: int = 2) -> None:
        self._checks = 0
        self._disconnect_after = disconnect_after
        self.client = None

    async def is_disconnected(self) -> bool:
        self._checks += 1
        return self._checks > self._disconnect_after


async def _collect(cache: PriceCache, disconnect_after: int = 1) -> list[str]:
    """Drain the SSE generator until it stops."""
    request = _FakeRequest(disconnect_after=disconnect_after)
    return [
        chunk
        async for chunk in _generate_events(cache, request, interval=0.001)  # type: ignore[arg-type]
    ]


def _payloads(chunks: list[str]) -> list[dict]:
    """Parse the data: frames out of the raw SSE chunks."""
    return [
        json.loads(c.removeprefix("data: ").strip())
        for c in chunks
        if c.startswith("data: ")
    ]


@pytest.mark.asyncio
class TestStreamContract:
    """The SSE wire contract the frontend depends on."""

    async def test_first_chunk_is_retry_directive(self):
        """The stream opens with a retry directive for EventSource."""
        chunks = await _collect(PriceCache())
        assert chunks[0] == "retry: 1000\n\n"

    async def test_full_snapshot_pushed_on_connect(self):
        """A client gets the whole cache immediately, not on the next tick."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("TSLA", 250.00)

        payloads = _payloads(await _collect(cache))

        assert payloads, "expected an immediate snapshot"
        assert set(payloads[0]) == {"AAPL", "TSLA"}

    async def test_event_shape_matches_plan_contract(self):
        """Each ticker value carries exactly the documented fields."""
        cache = PriceCache()
        cache.set_day_open("AAPL", 190.00)
        cache.update("AAPL", 199.50)

        payloads = _payloads(await _collect(cache))
        entry = payloads[0]["AAPL"]

        assert set(entry) == {
            "ticker", "price", "prev_price", "day_open",
            "change_pct", "timestamp", "direction",
        }
        assert entry["ticker"] == "AAPL"
        assert entry["price"] == 199.50
        assert entry["day_open"] == 190.00
        assert entry["change_pct"] == 5.0

    async def test_no_resend_while_version_unchanged(self):
        """An idle cache produces exactly one payload, not one per poll."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)

        payloads = _payloads(await _collect(cache, disconnect_after=5))

        assert len(payloads) == 1

    async def test_empty_cache_sends_no_data_frame(self):
        """With nothing tracked, only the retry directive goes out."""
        chunks = await _collect(PriceCache())
        assert _payloads(chunks) == []

    async def test_every_cached_ticker_is_streamed(self):
        """The stream covers whatever the cache tracks.

        Tracking is the union of watchlist and open positions, so a ticker held
        but no longer watched keeps streaming — the union itself is owned by
        the routes layer, which calls add_ticker/remove_ticker.
        """
        cache = PriceCache()
        cache.update("AAPL", 190.00)   # watchlist only
        cache.update("TSLA", 250.00)   # held but dropped from the watchlist

        payloads = _payloads(await _collect(cache))

        assert set(payloads[0]) == {"AAPL", "TSLA"}


class TestStreamRouter:
    """Router construction."""

    def test_router_exposes_the_prices_route(self):
        """The factory mounts GET /api/stream/prices."""
        router = create_stream_router(PriceCache())
        assert [r.path for r in router.routes] == ["/api/stream/prices"]

    def test_repeated_calls_do_not_stack_routes(self):
        """Each call yields a fresh router rather than accumulating routes."""
        first = create_stream_router(PriceCache())
        second = create_stream_router(PriceCache())
        assert len(first.routes) == 1
        assert len(second.routes) == 1
