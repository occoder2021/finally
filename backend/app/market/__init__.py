"""Market data subsystem for FinAlly.

Public API:
    PriceUpdate         - Immutable price snapshot dataclass
    PriceCache          - Thread-safe in-memory latest-price store
    PriceHistoryBuffer  - Bounded per-ticker recent price series
    MarketSinks         - Bundles cache + history behind one write call
    MarketDataSource    - Abstract interface for data providers
    create_market_data_source - Factory that selects simulator or Massive
    create_stream_router - FastAPI router factory for the SSE endpoint
    create_history_router - FastAPI router factory for the price history endpoint
"""

from .cache import PriceCache
from .factory import create_market_data_source
from .history import MAX_POINTS, PriceHistoryBuffer
from .interface import MarketDataSource
from .models import PriceUpdate
from .prices_route import create_history_router
from .sinks import MarketSinks
from .stream import create_stream_router

__all__ = [
    "MAX_POINTS",
    "MarketDataSource",
    "MarketSinks",
    "PriceCache",
    "PriceHistoryBuffer",
    "PriceUpdate",
    "create_history_router",
    "create_market_data_source",
    "create_stream_router",
]
