"""ポートフォリオ分析: セクター配分・相関行列を算出する。"""

import math

from database import get_db


def get_allocation() -> dict:
    """セクター別・市場別の資産配分を算出する。"""
    with get_db() as conn:
        holdings = conn.execute(
            "SELECT h.symbol, h.market, h.quantity, s.sector "
            "FROM portfolio_holdings h "
            "LEFT JOIN stocks s ON h.symbol = s.symbol AND h.market = s.market"
        ).fetchall()

        if not holdings:
            return {"by_market": [], "by_sector": []}

        # 各保有の時価を算出
        items = []
        for h in holdings:
            row = conn.execute(
                "SELECT close FROM daily_prices "
                "WHERE symbol = ? AND market = ? ORDER BY date DESC LIMIT 1",
                (h["symbol"], h["market"]),
            ).fetchone()
            price = row["close"] if row else 0
            value = h["quantity"] * price
            items.append({
                "symbol": h["symbol"],
                "market": h["market"],
                "sector": h["sector"] or "不明",
                "value": value,
            })

        total = sum(i["value"] for i in items)
        if total == 0:
            return {"by_market": [], "by_sector": []}

        # 市場別
        by_market: dict[str, float] = {}
        for i in items:
            by_market[i["market"]] = by_market.get(i["market"], 0) + i["value"]

        # セクター別
        by_sector: dict[str, float] = {}
        for i in items:
            by_sector[i["sector"]] = by_sector.get(i["sector"], 0) + i["value"]

        def to_list(d: dict[str, float]) -> list[dict]:
            return [
                {"label": k, "value": v, "percentage": v / total}
                for k, v in sorted(d.items(), key=lambda x: -x[1])
            ]

        return {
            "by_market": to_list(by_market),
            "by_sector": to_list(by_sector),
        }


def get_correlation() -> dict:
    """保有銘柄間の日次リターンのピアソン相関行列を算出する。"""
    with get_db() as conn:
        holdings = conn.execute(
            "SELECT symbol, market FROM portfolio_holdings"
        ).fetchall()

        if len(holdings) < 2:
            return {"symbols": [h["symbol"] for h in holdings], "matrix": []}

        # 各銘柄の日次リターンを取得
        returns_map: dict[str, list[tuple[str, float]]] = {}
        for h in holdings:
            rows = conn.execute(
                "SELECT date, close FROM daily_prices "
                "WHERE symbol = ? AND market = ? ORDER BY date ASC",
                (h["symbol"], h["market"]),
            ).fetchall()
            if len(rows) < 2:
                continue
            daily_returns = []
            for i in range(1, len(rows)):
                prev = rows[i - 1]["close"]
                if prev != 0:
                    daily_returns.append((rows[i]["date"], (rows[i]["close"] - prev) / prev))
            returns_map[h["symbol"]] = daily_returns

        symbols = [h["symbol"] for h in holdings if h["symbol"] in returns_map]
        if len(symbols) < 2:
            return {"symbols": symbols, "matrix": []}

        # 共通日付のリターンだけで相関を計算
        matrix = []
        for sym_a in symbols:
            row = []
            returns_a = dict(returns_map[sym_a])
            for sym_b in symbols:
                if sym_a == sym_b:
                    row.append(1.0)
                else:
                    returns_b = dict(returns_map[sym_b])
                    common_dates = set(returns_a.keys()) & set(returns_b.keys())
                    if len(common_dates) < 3:
                        row.append(None)
                        continue
                    vals_a = [returns_a[d] for d in sorted(common_dates)]
                    vals_b = [returns_b[d] for d in sorted(common_dates)]
                    row.append(_pearson(vals_a, vals_b))
            matrix.append(row)

        return {"symbols": symbols, "matrix": matrix}


def _pearson(x: list[float], y: list[float]) -> float | None:
    """ピアソン相関係数を計算する。"""
    n = len(x)
    if n < 3:
        return None
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x) / n)
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y) / n)
    if std_x == 0 or std_y == 0:
        return None
    return cov / (std_x * std_y)
