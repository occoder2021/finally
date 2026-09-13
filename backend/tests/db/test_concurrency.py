"""Concurrency property for execute_trade: overlapping requests can never
overspend cash or observe a partially applied trade.

Fires many buy trades at once from separate threads against one database
file and asserts: cash never goes negative, the number of successful trades
matches the trade log, and final cash exactly reconciles against the sum of
successful fills (no lost or double-counted writes).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.db import ApiError, execute_trade, get_cash_balance
from app.db.connection import get_connection
from app.db.money import round_cash


def _attempt_buy(quantity: float, price: float) -> tuple[bool, float]:
    try:
        result = execute_trade("AAPL", "buy", quantity, price)
        return True, result.total
    except ApiError as exc:
        assert exc.code == "INSUFFICIENT_CASH"
        return False, 0.0


def test_concurrent_buys_never_overspend_cash(db_path):
    # Starting cash: 10000.0. Each attempted buy costs 300.0, so at most 33
    # of 60 concurrent attempts can succeed (33 * 300 = 9900 <= 10000).
    price = 100.0
    quantity = 3.0
    cost = round_cash(quantity * price)
    attempts = 60

    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(_attempt_buy, quantity, price) for _ in range(attempts)]
        for future in as_completed(futures):
            results.append(future.result())

    successes = [total for ok, total in results if ok]
    failures = [ok for ok, _ in results if not ok]

    final_cash = get_cash_balance()
    assert final_cash >= 0.0

    expected_cash = round_cash(10000.0 - len(successes) * cost)
    assert final_cash == expected_cash

    # No thread should have been able to push cash negative, so the number
    # of successes is bounded by what cash actually allows.
    assert len(successes) <= 10000.0 // cost
    assert len(successes) + len(failures) == attempts

    with get_connection() as conn:
        trade_count = conn.execute(
            "SELECT COUNT(*) AS n FROM trades WHERE ticker = 'AAPL' AND side = 'buy'"
        ).fetchone()["n"]
    assert trade_count == len(successes)


def test_concurrent_buy_and_sell_keep_position_consistent(db_path):
    # Seed a position, then hammer it with concurrent sells that in total
    # exceed what's held -- some must fail, and the final position must
    # exactly match successful sells (no overselling, no lost writes).
    execute_trade("AAPL", "buy", 100, 50.0)

    def attempt_sell():
        try:
            result = execute_trade("AAPL", "sell", 5, 60.0)
            return True, result.quantity
        except ApiError as exc:
            assert exc.code == "INSUFFICIENT_SHARES"
            return False, 0.0

    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(attempt_sell) for _ in range(30)]
        for future in as_completed(futures):
            results.append(future.result())

    successes = [qty for ok, qty in results if ok]
    assert len(successes) == 20  # 100 shares / 5 per sell

    from app.db import get_position

    remaining = get_position("AAPL")
    assert remaining is None  # fully sold, row deleted

    final_cash = get_cash_balance()
    expected_cash = round_cash(10000.0 - 100 * 50.0 + 20 * 5 * 60.0)
    assert final_cash == expected_cash
