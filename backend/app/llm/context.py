"""Portfolio context and prompt construction for the chat assistant.

Deliberately has no dependency on `app.db` — it duck-types on `.ticker`,
`.quantity`, `.avg_cost` (positions) and `.role`, `.content` (history
messages), so it is fully unit-testable with plain fakes regardless of build
order between agents, and is reused as-is once the real types exist.
"""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """\
You are FinAlly, an AI trading assistant embedded in a simulated trading \
workstation. You help the user understand and manage a paper portfolio.

- Analyze portfolio composition, risk concentration, and P&L when asked.
- Suggest trades with clear, concise reasoning.
- Execute a trade only when the user has asked for it or agreed to it, by \
putting it in the `trades` field. Anything in `trades` executes immediately \
with real (simulated) money — a trade you are merely proposing belongs in \
`message`, not in `trades`.
- Manage the watchlist proactively via `watchlist_changes` when it helps \
the conversation (e.g. the user mentions a new ticker they're interested \
in, or asks to track/untrack one).
- Be concise and data-driven. No filler.
- If the user names a dollar amount instead of a share count (e.g. "buy \
$2,000 of NVDA"), convert it to a share quantity yourself using the current \
price and cash balance given in the portfolio context below — the schema \
only accepts share quantities.
- Always respond with the required structured JSON: `message` (your reply \
to show the user), `trades` (list, may be empty), and `watchlist_changes` \
(list, may be empty).
"""


def format_portfolio_context(
    cash_balance: float,
    positions: list[Any],
    watchlist: list[str],
    price_cache: Any,
) -> str:
    """Render cash, positions (with live P&L) and watchlist prices as plain
    text for the prompt. A ticker with no cached price is reported as
    unavailable rather than priced at zero, matching the rule the rest of
    the app follows for missing prices."""
    lines = [f"Cash balance: ${cash_balance:,.2f}"]

    if not positions:
        lines.append("Positions: none")
    else:
        lines.append("Positions:")
        for p in positions:
            price = price_cache.get_price(p.ticker)
            if price is None:
                lines.append(
                    f"  - {p.ticker}: {p.quantity:g} shares @ avg cost "
                    f"${p.avg_cost:.2f} (current price unavailable)"
                )
                continue
            market_value = price * p.quantity
            cost_basis = p.avg_cost * p.quantity
            pnl = market_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0
            lines.append(
                f"  - {p.ticker}: {p.quantity:g} shares @ avg cost ${p.avg_cost:.2f}, "
                f"current ${price:.2f}, market value ${market_value:,.2f}, "
                f"unrealized P&L ${pnl:,.2f} ({pnl_pct:+.2f}%)"
            )

    priced_market_value = sum(
        (price_cache.get_price(p.ticker) or 0.0) * p.quantity for p in positions
    )
    lines.append(f"Total portfolio value (priced holdings only): ${cash_balance + priced_market_value:,.2f}")

    if not watchlist:
        lines.append("Watchlist: none")
    else:
        lines.append("Watchlist:")
        for ticker in watchlist:
            price = price_cache.get_price(ticker)
            price_str = f"${price:.2f}" if price is not None else "unavailable"
            lines.append(f"  - {ticker}: {price_str}")

    return "\n".join(lines)


def build_messages(
    portfolio_context: str,
    history: list[Any],
    user_message: str,
) -> list[dict]:
    """Assemble the full LiteLLM message list: system prompt, portfolio
    context, bounded conversation history, then the new user message.

    `history` items duck-type on `.role` / `.content` and must already be
    bounded (last 20) and chronological — this function does not bound or
    reorder them.
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current portfolio context:\n{portfolio_context}"},
    ]
    for m in history:
        role = m.role if m.role in ("user", "assistant") else "user"
        messages.append({"role": role, "content": m.content})
    messages.append({"role": "user", "content": user_message})
    return messages
