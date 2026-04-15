"""バックグラウンドデータ収集: 登録済みウォッチリスト銘柄の日足データを自動取得する。"""

import logging
from datetime import date, timedelta

from database import get_db, utc_now_iso

logger = logging.getLogger(__name__)


async def collect_all(providers: dict) -> dict:
    """ウォッチリスト（watched=1）の全銘柄のデータを収集する。"""
    with get_db() as conn:
        stocks = conn.execute(
            "SELECT symbol, market FROM stocks WHERE watched = 1"
        ).fetchall()

    if not stocks:
        logger.info("No watched stocks to collect.")
        return {"collected": 0, "errors": 0}

    collected = 0
    errors = 0

    for s in stocks:
        symbol = s["symbol"]
        market = s["market"]
        provider = providers.get(market)
        if provider is None:
            logger.warning("No provider for market %s, skipping %s", market, symbol)
            continue

        try:
            # 最新日付の翌日から今日まで取得
            with get_db() as conn:
                last_row = conn.execute(
                    "SELECT date FROM daily_prices "
                    "WHERE symbol = ? AND market = ? ORDER BY date DESC LIMIT 1",
                    (symbol, market),
                ).fetchone()

            if last_row:
                start = date.fromisoformat(last_row["date"]) + timedelta(days=1)
            else:
                start = date(2024, 1, 1)

            end = date.today()
            if start > end:
                logger.info("No new data for %s:%s (up to date)", market, symbol)
                continue

            prices = await provider.get_daily_prices(symbol, start, end)

            with get_db() as conn:
                for p in prices:
                    conn.execute(
                        "INSERT OR REPLACE INTO daily_prices "
                        "(symbol, market, date, open, high, low, close, volume, adj_close) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (symbol, market, p.date.isoformat(),
                         p.open, p.high, p.low, p.close, p.volume, p.adj_close),
                    )
                conn.execute(
                    "INSERT INTO collection_log (market, symbol, fetched_at, status, message) "
                    "VALUES (?, ?, ?, 'OK', ?)",
                    (market, symbol, utc_now_iso(), f"Fetched {len(prices)} records"),
                )
                conn.commit()

            collected += 1
            logger.info("Collected %d prices for %s:%s", len(prices), market, symbol)

        except Exception as e:
            errors += 1
            logger.exception("Failed to collect %s:%s", market, symbol)
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO collection_log (market, symbol, fetched_at, status, message) "
                    "VALUES (?, ?, ?, 'ERROR', ?)",
                    (market, symbol, utc_now_iso(), str(e)),
                )
                conn.commit()

    return {"collected": collected, "errors": errors}
