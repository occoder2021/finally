"""Tests for PriceHistoryBuffer."""

import threading

from app.market.history import MAX_POINTS, PriceHistoryBuffer


class TestPriceHistoryBuffer:
    """Unit tests for the bounded per-ticker history buffer."""

    def test_unknown_ticker_returns_empty_list(self):
        """An unknown ticker returns [] rather than raising."""
        buf = PriceHistoryBuffer()
        assert buf.get("NOPE") == []

    def test_append_and_get(self):
        """Points come back as dicts with timestamp and price."""
        buf = PriceHistoryBuffer()
        buf.append("AAPL", 190.00, 1000.0)
        buf.append("AAPL", 191.00, 1001.0)

        points = buf.get("AAPL")
        assert points == [
            {"timestamp": 1000.0, "price": 190.00},
            {"timestamp": 1001.0, "price": 191.00},
        ]

    def test_ordering_is_oldest_first(self):
        """Points are returned in insertion order, oldest first."""
        buf = PriceHistoryBuffer()
        for i in range(10):
            buf.append("AAPL", 100.0 + i, float(i))

        points = buf.get("AAPL")
        timestamps = [p["timestamp"] for p in points]
        assert timestamps == sorted(timestamps)
        assert points[0]["price"] == 100.0
        assert points[-1]["price"] == 109.0

    def test_respects_maxlen_evicting_oldest(self):
        """Appending past max_points evicts the oldest points first."""
        buf = PriceHistoryBuffer(max_points=5)
        for i in range(20):
            buf.append("AAPL", float(i), float(i))

        points = buf.get("AAPL")
        assert len(points) == 5
        # Only the last five survive
        assert [p["price"] for p in points] == [15.0, 16.0, 17.0, 18.0, 19.0]

    def test_default_max_points(self):
        """Default cap matches the documented MAX_POINTS."""
        buf = PriceHistoryBuffer()
        assert buf.max_points == MAX_POINTS

        for i in range(MAX_POINTS + 50):
            buf.append("AAPL", float(i), float(i))

        assert len(buf.get("AAPL")) == MAX_POINTS

    def test_tickers_are_independent(self):
        """Each ticker gets its own buffer."""
        buf = PriceHistoryBuffer(max_points=3)
        buf.append("AAPL", 190.0, 1.0)
        buf.append("TSLA", 250.0, 1.0)

        assert len(buf.get("AAPL")) == 1
        assert len(buf.get("TSLA")) == 1
        assert buf.get("AAPL")[0]["price"] == 190.0

    def test_remove_drops_history(self):
        """remove() clears a ticker's series."""
        buf = PriceHistoryBuffer()
        buf.append("AAPL", 190.0, 1.0)
        buf.remove("AAPL")
        assert buf.get("AAPL") == []

    def test_remove_unknown_ticker_is_noop(self):
        """Removing a ticker that was never tracked does not raise."""
        buf = PriceHistoryBuffer()
        buf.remove("NOPE")

    def test_tickers_lists_only_populated(self):
        """tickers() reports tickers holding at least one point."""
        buf = PriceHistoryBuffer()
        buf.append("AAPL", 190.0, 1.0)
        assert buf.tickers() == ["AAPL"]

    def test_thread_safety_under_concurrent_appends(self):
        """Concurrent appends never corrupt the buffer or lose the cap."""
        buf = PriceHistoryBuffer(max_points=1000)
        errors: list[Exception] = []

        def writer(offset: int) -> None:
            try:
                for i in range(100):
                    buf.append("AAPL", float(offset + i), float(offset + i))
                    buf.get("AAPL")  # concurrent read
            except Exception as e:  # pragma: no cover - failure path
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i * 100,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(buf.get("AAPL")) == 800
