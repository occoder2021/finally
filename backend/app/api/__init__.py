"""Application API layer: REST routers, wiring, and error handling.

Public API:
    create_portfolio_router  - GET/POST /api/portfolio*
    create_watchlist_router  - GET/POST/DELETE /api/watchlist*
    install_exception_handlers - single error-envelope handler (TEAM_CONTRACT §4)
    get_db_module             - FastAPI dependency resolving app.db lazily
    SnapshotTask               - 30s portfolio valuation background task
    mount_static               - serves the Next.js static export as a catch-all
"""

from .background import SnapshotTask
from .deps import get_db_module
from .errors import install_exception_handlers
from .portfolio import create_portfolio_router
from .static import mount_static
from .watchlist import create_watchlist_router

__all__ = [
    "SnapshotTask",
    "create_portfolio_router",
    "create_watchlist_router",
    "get_db_module",
    "install_exception_handlers",
    "mount_static",
]
