"""Tests for the day-open reference price and session change %."""

from unittest.mock import MagicMock, patch

import pytest

from app.market.cache import PriceCache
from app.market.history import PriceHistoryBuffer
from app.market.massive_client import MassiveDataSource
from app.market.seed_prices import SEED_PRICES
from app.market.simulator import SimulatorDataSource
from app.market.sinks import MarketSinks


class TestPriceCacheDayOpen:
    """day_open must be set once and survive every later tick."""

    def test_first_price_becomes_day_open(self):
        """With no explicit day-open, the first price recorded becomes it."""
        cache = PriceCache()
        update = cache.update("AAPL", 190.00)
        assert update.day_open == 190.00

    def test_day_open_survives_later_ticks(self):
        """Later prices never move the day-open reference."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        for price in (191.0, 195.0, 180.0):
            update = cache.update("AAPL", price)
            assert update.day_open == 190.00

    def test_set_day_open_first_write_wins(self):
        """set_day_open is idempotent — repeated calls do not overwrite."""
        cache = PriceCache()
        cache.set_day_open("AAPL", 190.00)
        cache.set_day_open("AAPL", 500.00)
        assert cache.get_day_open("AAPL") == 190.00

    def test_set_day_open_precedes_first_tick(self):
        """An explicit day-open is used even if the first tick differs."""
        cache = PriceCache()
        cache.set_day_open("AAPL", 185.00)
        update = cache.update("AAPL", 190.00)
        assert update.day_open == 185.00
        assert update.day_change_percent == pytest.approx(2.7027, abs=1e-3)

    def test_get_day_open_unknown_ticker(self):
        """Unknown tickers have no day-open."""
        assert PriceCache().get_day_open("NOPE") is None

    def test_remove_clears_day_open(self):
        """Removing a ticker clears its day-open so a re-add re-baselines."""
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.remove("AAPL")
        assert cache.get_day_open("AAPL") is None

        cache.update("AAPL", 250.00)
        assert cache.get_day_open("AAPL") == 250.00

    def test_day_open_rounded_to_cents(self):
        """The reference is stored at cent precision, like prices."""
        cache = PriceCache()
        cache.set_day_open("AAPL", 190.005678)
        assert cache.get_day_open("AAPL") == 190.01


@pytest.mark.asyncio
class TestSimulatorDayOpen:
    """The simulator's day-open is the seed price, for the life of the process."""

    async def test_day_open_equals_seed_price(self):
        """Seeded tickers baseline on their documented seed price."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())
        source = SimulatorDataSource(sinks=sinks, update_interval=0.01)
        await source.start(["AAPL", "NVDA"])

        assert cache.get_day_open("AAPL") == SEED_PRICES["AAPL"]
        assert cache.get_day_open("NVDA") == SEED_PRICES["NVDA"]

        await source.stop()

    async def test_day_open_stable_across_ticks(self):
        """Many ticks later, the reference is unchanged."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())
        source = SimulatorDataSource(sinks=sinks, update_interval=0.01)
        await source.start(["AAPL"])

        import asyncio

        await asyncio.sleep(0.1)  # several ticks
        await source.stop()

        assert cache.version > 1  # prices really did move on
        assert cache.get_day_open("AAPL") == SEED_PRICES["AAPL"]
        assert cache.get("AAPL").day_open == SEED_PRICES["AAPL"]

    async def test_added_ticker_gets_its_own_day_open(self):
        """A ticker added at runtime baselines on its own first price."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())
        source = SimulatorDataSource(sinks=sinks, update_interval=0.01)
        await source.start(["AAPL"])
        await source.add_ticker("TSLA")

        assert cache.get_day_open("TSLA") == SEED_PRICES["TSLA"]

        await source.stop()


def _snapshot(ticker: str, price: float, timestamp_ms: int, prev_close=None) -> MagicMock:
    """Mock Massive snapshot; prev_close=None means the field is unavailable."""
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade = MagicMock()
    snap.last_trade.price = price
    snap.last_trade.timestamp = timestamp_ms
    if prev_close is None:
        snap.prev_day = None
    else:
        snap.prev_day = MagicMock()
        snap.prev_day.close = prev_close
    return snap


@pytest.mark.asyncio
class TestMassiveDayOpen:
    """Massive baselines on the prior trading day's close when available."""

    async def _poll(self, snapshots) -> PriceCache:
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())
        source = MassiveDataSource(api_key="test-key", sinks=sinks, poll_interval=60.0)
        source._tickers = [s.ticker for s in snapshots]
        source._client = MagicMock()
        with patch.object(source, "_fetch_snapshots", return_value=snapshots):
            await source._poll_once()
        return cache

    async def test_day_open_from_prev_day_close(self):
        """prev_day.close is the day-open reference."""
        cache = await self._poll([_snapshot("AAPL", 190.50, 1707580800000, prev_close=185.00)])
        assert cache.get_day_open("AAPL") == 185.00

    async def test_session_change_computed_against_prev_close(self):
        """change_pct reflects the move from the prior close."""
        cache = await self._poll([_snapshot("AAPL", 200.00, 1707580800000, prev_close=190.00)])
        wire = cache.get("AAPL").to_dict()
        assert wire["day_open"] == 190.00
        assert wire["change_pct"] == pytest.approx(5.2632, abs=1e-3)

    async def test_falls_back_to_first_price_when_prev_day_missing(self):
        """A missing prev_day falls back to the first price seen."""
        cache = await self._poll([_snapshot("AAPL", 190.50, 1707580800000, prev_close=None)])
        assert cache.get_day_open("AAPL") == 190.50

    async def test_falls_back_when_close_is_not_numeric(self):
        """A non-numeric close (e.g. an unset mock attr) falls back safely."""
        snap = _snapshot("AAPL", 190.50, 1707580800000, prev_close=None)
        snap.prev_day = MagicMock()  # .close is itself a MagicMock, not a number
        cache = await self._poll([snap])
        assert cache.get_day_open("AAPL") == 190.50

    async def test_day_open_not_recomputed_on_later_polls(self):
        """The reference is set on first sight and not touched again."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())
        source = MassiveDataSource(api_key="test-key", sinks=sinks, poll_interval=60.0)
        source._tickers = ["AAPL"]
        source._client = MagicMock()

        first = [_snapshot("AAPL", 190.00, 1707580800000, prev_close=185.00)]
        second = [_snapshot("AAPL", 195.00, 1707580900000, prev_close=999.00)]

        with patch.object(source, "_fetch_snapshots", return_value=first):
            await source._poll_once()
        with patch.object(source, "_fetch_snapshots", return_value=second):
            await source._poll_once()

        assert cache.get_day_open("AAPL") == 185.00
        assert cache.get_price("AAPL") == 195.00
