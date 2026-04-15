"""銘柄スクリーニング: 出来高・ボラティリティ等でフィルタ・ソートする。"""

import math

from database import get_db


def screen_stocks(
    market: str | None = None,
    sector: str | None = None,
    min_volume: int | None = None,
    max_volume: int | None = None,
    min_volatility: float | None = None,
    max_volatility: float | None = None,
    sort_by: str = "volume",
    days: int = 20,
) -> list[dict]:
    """登録銘柄を条件でフィルタし、スクリーニング結果を返す。"""
    with get_db() as conn:
        query = "SELECT symbol, market, name, sector FROM stocks WHERE 1=1"
        params: list = []
        if market:
            query += " AND market = ?"
            params.append(market)
        if sector:
            query += " AND sector = ?"
            params.append(sector)

        stocks = conn.execute(query, params).fetchall()

        results = []
        for s in stocks:
            rows = conn.execute(
                "SELECT close, volume FROM daily_prices "
                "WHERE symbol = ? AND market = ? "
                "ORDER BY date DESC LIMIT ?",
                (s["symbol"], s["market"], days),
            ).fetchall()

            if len(rows) < 2:
                continue

            closes = [r["close"] for r in rows]
            volumes = [r["volume"] for r in rows]

            avg_volume = sum(volumes) / len(volumes)
            latest_close = closes[0]

            # 日次リターンの標準偏差 = ボラティリティ
            returns = [
                (closes[i] - closes[i + 1]) / closes[i + 1]
                for i in range(len(closes) - 1)
                if closes[i + 1] != 0
            ]
            volatility = _std(returns) if returns else 0.0

            # 変動率 = (最新 - 最古) / 最古
            oldest_close = closes[-1]
            change_pct = (latest_close - oldest_close) / oldest_close if oldest_close != 0 else 0.0

            # フィルタ適用
            if min_volume is not None and avg_volume < min_volume:
                continue
            if max_volume is not None and avg_volume > max_volume:
                continue
            if min_volatility is not None and volatility < min_volatility:
                continue
            if max_volatility is not None and volatility > max_volatility:
                continue

            results.append({
                "symbol": s["symbol"],
                "market": s["market"],
                "name": s["name"],
                "sector": s["sector"],
                "close": latest_close,
                "volume": volumes[0],
                "avg_volume": avg_volume,
                "volatility": volatility,
                "change_pct": change_pct,
            })

        # ソート
        sort_keys = {
            "volume": lambda r: r["avg_volume"],
            "volatility": lambda r: r["volatility"],
            "change_pct": lambda r: r["change_pct"],
        }
        key_fn = sort_keys.get(sort_by, sort_keys["volume"])
        results.sort(key=key_fn, reverse=True)

        return results


def _std(values: list[float]) -> float:
    """標準偏差を計算する。"""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return math.sqrt(variance)
