"""LLM chat integration: `POST /api/chat` and `GET /api/chat/history`.

Owned exclusively by the llm-engineer per TEAM_CONTRACT.md §7. Exposes only
the router factory — `main.py` (owned by backend-api) mounts it.
"""

from .router import create_chat_router

__all__ = ["create_chat_router"]
