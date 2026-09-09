"""Tests for PriceUpdate dataclass."""

import pytest

from app.market.models import PriceUpdate


class TestPriceUpdate:
    """Unit tests for the PriceUpdate model."""

    def test_price_update_creation(self):
        """Test basic PriceUpdate creation."""
        update = PriceUpdate(
            ticker="AAPL", price=190.50, previous_price=190.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        assert update.ticker == "AAPL"
        assert update.price == 190.50
        assert update.previous_price == 190.00
        assert update.day_open == 190.00
        assert update.timestamp == 1234567890.0

    def test_change_calculation(self):
        """Test price change calculation."""
        update = PriceUpdate(
            ticker="AAPL", price=190.50, previous_price=190.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        assert update.change == 0.50

    def test_change_negative(self):
        """Test negative price change."""
        update = PriceUpdate(
            ticker="AAPL", price=189.50, previous_price=190.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        assert update.change == -0.50

    def test_change_percent_up(self):
        """Test tick-over-tick percentage change (up)."""
        update = PriceUpdate(
            ticker="AAPL", price=190.00, previous_price=100.00,
            day_open=100.00, timestamp=1234567890.0,
        )
        assert update.change_percent == 90.0

    def test_change_percent_down(self):
        """Test tick-over-tick percentage change (down)."""
        update = PriceUpdate(
            ticker="AAPL", price=100.00, previous_price=200.00,
            day_open=200.00, timestamp=1234567890.0,
        )
        assert update.change_percent == -50.0

    def test_change_percent_zero_previous(self):
        """Test percentage change with zero previous price."""
        update = PriceUpdate(
            ticker="AAPL", price=100.00, previous_price=0.00,
            day_open=100.00, timestamp=1234567890.0,
        )
        assert update.change_percent == 0.0

    def test_day_change_percent_up(self):
        """Session change is measured against day_open, not the previous tick."""
        update = PriceUpdate(
            ticker="AAPL", price=209.00, previous_price=208.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        assert update.day_change_percent == 10.0

    def test_day_change_percent_down(self):
        """Session change goes negative below the day-open reference."""
        update = PriceUpdate(
            ticker="AAPL", price=171.00, previous_price=172.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        assert update.day_change_percent == -10.0

    def test_day_change_percent_differs_from_tick_change(self):
        """A price up on the tick can still be down on the session."""
        update = PriceUpdate(
            ticker="AAPL", price=180.00, previous_price=179.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        assert update.direction == "up"
        assert update.change_percent > 0
        assert update.day_change_percent < 0

    def test_day_change_percent_zero_day_open(self):
        """Guard against division by zero when day_open is 0."""
        update = PriceUpdate(
            ticker="AAPL", price=100.00, previous_price=100.00,
            day_open=0.0, timestamp=1234567890.0,
        )
        assert update.day_change_percent == 0.0

    def test_direction_up(self):
        """Test direction calculation (up)."""
        update = PriceUpdate(
            ticker="AAPL", price=191.00, previous_price=190.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        assert update.direction == "up"

    def test_direction_down(self):
        """Test direction calculation (down)."""
        update = PriceUpdate(
            ticker="AAPL", price=189.00, previous_price=190.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        assert update.direction == "down"

    def test_direction_flat(self):
        """Test direction calculation (flat)."""
        update = PriceUpdate(
            ticker="AAPL", price=190.00, previous_price=190.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        assert update.direction == "flat"

    def test_to_dict(self):
        """to_dict emits exactly the PLAN.md wire contract."""
        update = PriceUpdate(
            ticker="AAPL", price=199.50, previous_price=199.00,
            day_open=190.00, timestamp=1234567890.0,
        )
        result = update.to_dict()

        assert set(result) == {
            "ticker", "price", "prev_price", "day_open",
            "change_pct", "timestamp", "direction",
        }
        assert result["ticker"] == "AAPL"
        assert result["price"] == 199.50
        assert result["prev_price"] == 199.00
        assert result["day_open"] == 190.00
        assert result["timestamp"] == 1234567890.0
        assert result["direction"] == "up"
        # change_pct is the session change vs. day_open, not the tick change
        assert result["change_pct"] == 5.0

    def test_immutability(self):
        """Test that PriceUpdate is immutable."""
        update = PriceUpdate(
            ticker="AAPL", price=190.50, previous_price=190.00,
            day_open=190.00, timestamp=1234567890.0,
        )

        with pytest.raises(AttributeError):
            update.price = 200.00  # Should raise error
