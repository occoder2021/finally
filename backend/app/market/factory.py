"""Factory for creating market data sources."""

from __future__ import annotations

import logging
import os

from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource
from .sinks import MarketSinks

logger = logging.getLogger(__name__)


def create_market_data_source(sinks: MarketSinks) -> MarketDataSource:
    """Create the appropriate market data source based on environment variables.

    - MASSIVE_API_KEY set and non-empty -> MassiveDataSource (real market data)
    - Otherwise -> SimulatorDataSource (GBM simulation)

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, sinks=sinks)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(sinks=sinks)
