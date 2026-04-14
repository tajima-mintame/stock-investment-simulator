from config import SUPPORTED_MARKETS
from database import get_db, utc_now_iso


def execute_trade(
    symbol: str,
    market: str,
    side: str,
    quantity: int,
    price: float,
    note: str | None = None,
) -> dict:
    """仮想取引を実行する。残高・保有を更新し、取引レコードを返す。"""
    if not symbol or not isinstance(symbol, str):
        raise ValueError("symbol is required")
    if market not in SUPPORTED_MARKETS:
        raise ValueError(f"market must be one of {SUPPORTED_MARKETS}")
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if price <= 0:
        raise ValueError("price must be positive")

    total_cost = price * quantity
    with get_db() as conn:
        stock = conn.execute(
            "SELECT symbol FROM stocks WHERE symbol = ? AND market = ?",
            (symbol, market),
        ).fetchone()
        if stock is None:
            raise ValueError(f"Stock {market}:{symbol} not found. Sync it first.")

        if side == "BUY":
            _execute_buy(conn, symbol, market, quantity, price, total_cost)
        else:
            _execute_sell(conn, symbol, market, quantity, price, total_cost)

        now = utc_now_iso()
        cursor = conn.execute(
            "INSERT INTO trades (symbol, market, side, quantity, price, executed_at, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (symbol, market, side, quantity, price, now, note),
        )
        conn.commit()

        return {
            "id": cursor.lastrowid,
            "symbol": symbol,
            "market": market,
            "side": side,
            "quantity": quantity,
            "price": price,
            "executed_at": now,
            "note": note,
        }


def _execute_buy(conn, symbol, market, quantity, price, total_cost):
    """買い注文: 残高チェック → 残高減算 → 保有更新。"""
    account = conn.execute("SELECT cash_balance FROM account WHERE id = 1").fetchone()
    if account["cash_balance"] < total_cost:
        raise ValueError(
            f"Insufficient balance: {account['cash_balance']:.0f} < {total_cost:.0f}"
        )

    conn.execute(
        "UPDATE account SET cash_balance = cash_balance - ? WHERE id = 1",
        (total_cost,),
    )

    holding = conn.execute(
        "SELECT quantity, avg_cost FROM portfolio_holdings WHERE symbol = ? AND market = ?",
        (symbol, market),
    ).fetchone()

    if holding is None:
        conn.execute(
            "INSERT INTO portfolio_holdings (symbol, market, quantity, avg_cost) "
            "VALUES (?, ?, ?, ?)",
            (symbol, market, quantity, price),
        )
    else:
        new_qty = holding["quantity"] + quantity
        new_avg = (
            (holding["avg_cost"] * holding["quantity"]) + (price * quantity)
        ) / new_qty
        conn.execute(
            "UPDATE portfolio_holdings SET quantity = ?, avg_cost = ? "
            "WHERE symbol = ? AND market = ?",
            (new_qty, new_avg, symbol, market),
        )


def _execute_sell(conn, symbol, market, quantity, price, total_cost):
    """売り注文: 保有チェック → 残高加算 → 保有更新。"""
    holding = conn.execute(
        "SELECT quantity, avg_cost FROM portfolio_holdings WHERE symbol = ? AND market = ?",
        (symbol, market),
    ).fetchone()

    if holding is None or holding["quantity"] < quantity:
        current = holding["quantity"] if holding else 0
        raise ValueError(
            f"Insufficient holdings: have {current}, trying to sell {quantity}"
        )

    conn.execute(
        "UPDATE account SET cash_balance = cash_balance + ? WHERE id = 1",
        (total_cost,),
    )

    new_qty = holding["quantity"] - quantity
    if new_qty == 0:
        conn.execute(
            "DELETE FROM portfolio_holdings WHERE symbol = ? AND market = ?",
            (symbol, market),
        )
    else:
        conn.execute(
            "UPDATE portfolio_holdings SET quantity = ? WHERE symbol = ? AND market = ?",
            (new_qty, symbol, market),
        )


def _get_latest_price(conn, symbol: str, market: str) -> float | None:
    """銘柄の最新終値を取得する。"""
    row = conn.execute(
        "SELECT close FROM daily_prices "
        "WHERE symbol = ? AND market = ? ORDER BY date DESC LIMIT 1",
        (symbol, market),
    ).fetchone()
    return row["close"] if row else None


def get_account_info() -> dict:
    """口座情報（残高 + ポートフォリオ時価総額）を取得する。"""
    with get_db() as conn:
        account = conn.execute("SELECT cash_balance FROM account WHERE id = 1").fetchone()
        cash = account["cash_balance"]

        holdings = conn.execute(
            "SELECT symbol, market, quantity FROM portfolio_holdings"
        ).fetchall()

        portfolio_value = 0.0
        for h in holdings:
            price = _get_latest_price(conn, h["symbol"], h["market"])
            if price is not None:
                portfolio_value += h["quantity"] * price

        return {
            "cash_balance": cash,
            "portfolio_value": portfolio_value,
            "total_value": cash + portfolio_value,
        }


def _calculate_fifo_pnls(trades) -> list[float]:
    """FIFO方式で実現損益を計算する。"""
    positions: dict[tuple[str, str], list[tuple[int, float]]] = {}
    realized_pnls: list[float] = []

    for t in trades:
        key = (t["symbol"], t["market"])
        if t["side"] == "BUY":
            positions.setdefault(key, []).append((t["quantity"], t["price"]))
        else:
            remaining = t["quantity"]
            sell_price = t["price"]
            lots = positions.get(key, [])
            pnl = 0.0

            while remaining > 0 and lots:
                lot_qty, lot_price = lots[0]
                matched = min(remaining, lot_qty)
                pnl += matched * (sell_price - lot_price)
                remaining -= matched
                if matched == lot_qty:
                    lots.pop(0)
                else:
                    lots[0] = (lot_qty - matched, lot_price)

            realized_pnls.append(pnl)

    return realized_pnls


def _compute_stats(total_trades: int, realized_pnls: list[float]) -> dict:
    """実現損益リストから統計値を算出する。"""
    gains = [p for p in realized_pnls if p > 0]
    losses = [p for p in realized_pnls if p <= 0]
    return {
        "total_trades": total_trades,
        "total_realized_pnl": sum(realized_pnls),
        "win_count": len(gains),
        "lose_count": len(losses),
        "win_rate": len(gains) / len(realized_pnls) if realized_pnls else 0.0,
        "avg_gain": sum(gains) / len(gains) if gains else 0.0,
        "avg_loss": sum(losses) / len(losses) if losses else 0.0,
    }


_EMPTY_STATS = {
    "total_trades": 0,
    "total_realized_pnl": 0.0,
    "win_count": 0,
    "lose_count": 0,
    "win_rate": 0.0,
    "avg_gain": 0.0,
    "avg_loss": 0.0,
}


def get_trade_stats() -> dict:
    """損益統計を算出する。"""
    with get_db() as conn:
        trades = conn.execute(
            "SELECT symbol, market, side, quantity, price "
            "FROM trades ORDER BY executed_at ASC"
        ).fetchall()

        if not trades:
            return dict(_EMPTY_STATS)

        return _compute_stats(len(trades), _calculate_fifo_pnls(trades))


def get_portfolio_holdings() -> list[dict]:
    """保有銘柄一覧（含み損益付き）を取得する。"""
    with get_db() as conn:
        holdings = conn.execute(
            "SELECT h.symbol, h.market, h.quantity, h.avg_cost, s.name "
            "FROM portfolio_holdings h "
            "LEFT JOIN stocks s ON h.symbol = s.symbol AND h.market = s.market"
        ).fetchall()

        result = []
        for h in holdings:
            current_price = _get_latest_price(conn, h["symbol"], h["market"])
            unrealized = None
            if current_price is not None:
                unrealized = (current_price - h["avg_cost"]) * h["quantity"]

            result.append({
                "symbol": h["symbol"],
                "market": h["market"],
                "name": h["name"],
                "quantity": h["quantity"],
                "avg_cost": h["avg_cost"],
                "current_price": current_price,
                "unrealized_pnl": unrealized,
            })

        return result
