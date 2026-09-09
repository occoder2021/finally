"""Tests for market data source factory."""

import os
from unittest.mock import patch

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.history import PriceHistoryBuffer
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource
from app.market.sinks import MarketSinks


class TestFactory:
    """Tests for create_market_data_source factory."""

    def test_creates_simulator_when_no_api_key(self):
        """Test that simulator is created when MASSIVE_API_KEY is not set."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())

        with patch.dict(os.environ, {}, clear=True):
            source = create_market_data_source(sinks)

        assert isinstance(source, SimulatorDataSource)

    def test_creates_simulator_when_api_key_empty(self):
        """Test that simulator is created when MASSIVE_API_KEY is empty."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())

        with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}, clear=True):
            source = create_market_data_source(sinks)

        assert isinstance(source, SimulatorDataSource)

    def test_creates_simulator_when_api_key_whitespace(self):
        """Test that simulator is created when MASSIVE_API_KEY is whitespace."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())

        with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}, clear=True):
            source = create_market_data_source(sinks)

        assert isinstance(source, SimulatorDataSource)

    def test_creates_massive_when_api_key_set(self):
        """Test that Massive client is created when MASSIVE_API_KEY is set."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())

        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}, clear=True):
            source = create_market_data_source(sinks)

        assert isinstance(source, MassiveDataSource)

    def test_massive_receives_api_key(self):
        """Test that Massive client receives the API key."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())

        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key-123"}, clear=True):
            source = create_market_data_source(sinks)

        assert isinstance(source, MassiveDataSource)
        assert source._api_key == "test-key-123"

    def test_simulator_receives_sinks(self):
        """Test that simulator receives the sinks reference."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())

        with patch.dict(os.environ, {}, clear=True):
            source = create_market_data_source(sinks)

        assert isinstance(source, SimulatorDataSource)
        assert source._sinks is sinks

    def test_massive_receives_sinks(self):
        """Test that Massive client receives the sinks reference."""
        cache = PriceCache()
        sinks = MarketSinks(cache, PriceHistoryBuffer())

        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}, clear=True):
            source = create_market_data_source(sinks)

        assert isinstance(source, MassiveDataSource)
        assert source._sinks is sinks
