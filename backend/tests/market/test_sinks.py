"""Tests for MarketSinks — the single write path to cache + history."""

from app.market.cache import PriceCache
from app.market.history import PriceHistoryBuffer
from app.market.sinks import MarketSinks


class TestMarketSinks:
    """One record() call must keep both sinks consistent."""

    def test_record_writes_to_both_sinks(self):
        """A single record() lands in the cache and the history buffer."""
        cache = PriceCache()
        history = PriceHistoryBuffer()
        sinks = MarketSinks(cache, history)

        sinks.record("AAPL", 190.00, timestamp=1000.0)

        assert cache.get_price("AAPL") == 190.00
        assert history.get("AAPL") == [{"timestamp": 1000.0, "price": 190.00}]

    def test_record_shares_one_timestamp(self):
        """Cache and history record the same timestamp for the same tick."""
        cache = PriceCache()
        history = PriceHistoryBuffer()
        sinks = MarketSinks(cache, history)

        update = sinks.record("AAPL", 190.00)

        point = history.get("AAPL")[0]
        assert point["timestamp"] == update.timestamp

    def test_record_shares_the_rounded_price(self):
        """History stores the cache's rounded price, so the two cannot drift."""
        cache = PriceCache()
        history = PriceHistoryBuffer()
        sinks = MarketSinks(cache, history)

        update = sinks.record("AAPL", 190.005678)

        assert update.price == 190.01
        assert history.get("AAPL")[0]["price"] == 190.01
        assert history.get("AAPL")[0]["price"] == cache.get_price("AAPL")

    def test_record_returns_the_price_update(self):
        """record() hands back the PriceUpdate the cache created."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())

        update = sinks.record("AAPL", 190.00)

        assert update.ticker == "AAPL"
        assert update is cache.get("AAPL")

    def test_sequence_of_records_stays_aligned(self):
        """Every cache version bump has exactly one history point behind it."""
        cache = PriceCache()
        history = PriceHistoryBuffer()
        sinks = MarketSinks(cache, history)

        for i in range(25):
            sinks.record("AAPL", 190.00 + i, timestamp=float(i))

        assert cache.version == 25
        assert len(history.get("AAPL")) == 25
        assert history.get("AAPL")[-1]["price"] == cache.get_price("AAPL")

    def test_remove_clears_both_sinks(self):
        """remove() drops the ticker from cache and history together."""
        cache = PriceCache()
        history = PriceHistoryBuffer()
        sinks = MarketSinks(cache, history)

        sinks.record("AAPL", 190.00)
        sinks.remove("AAPL")

        assert cache.get("AAPL") is None
        assert history.get("AAPL") == []
