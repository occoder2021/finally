"""SQLite persistence layer for FinAlly.

Public API (TEAM_CONTRACT.md 5):

    init_db, get_connection, reset_db_for_tests
    ApiError
    round_cash, round_qty, is_zero_qty
    get_cash_balance, get_positions, get_position
    execute_trade
    get_watchlist, add_to_watchlist, remove_from_watchlist
    get_tracked_tickers
    record_snapshot, get_snapshots, prune_snapshots
    get_chat_messages, append_chat_message

Also exported for convenience (used as return/parameter types by the above):
`Position`, `TradeResult`, `ChatMessage`, and `normalize_ticker` (the one
ticker-normalization implementation, used internally by the watchlist
functions and available to callers that want to validate/normalize a ticker
before calling into this package).
"""

from .chat import append_chat_message, get_chat_messages
from .connection import get_connection, init_db, reset_db_for_tests
from .errors import ApiError
from .models import ChatMessage, Position, TradeResult
from .money import CASH_DP, QTY_DP, QTY_EPSILON, is_zero_qty, round_cash, round_qty
from .portfolio import execute_trade, get_cash_balance, get_position, get_positions
from .snapshots import get_snapshots, prune_snapshots, record_snapshot
from .tickers import normalize_ticker
from .watchlist import (
    WATCHLIST_MAX,
    add_to_watchlist,
    get_tracked_tickers,
    get_watchlist,
    remove_from_watchlist,
)

__all__ = [
    "CASH_DP",
    "QTY_DP",
    "QTY_EPSILON",
    "WATCHLIST_MAX",
    "ApiError",
    "ChatMessage",
    "Position",
    "TradeResult",
    "add_to_watchlist",
    "append_chat_message",
    "execute_trade",
    "get_cash_balance",
    "get_chat_messages",
    "get_connection",
    "get_position",
    "get_positions",
    "get_snapshots",
    "get_tracked_tickers",
    "get_watchlist",
    "init_db",
    "is_zero_qty",
    "normalize_ticker",
    "prune_snapshots",
    "record_snapshot",
    "remove_from_watchlist",
    "reset_db_for_tests",
    "round_cash",
    "round_qty",
]
