"""テスト用共通ヘルパー関数。"""

from datetime import date, timedelta

from database import get_db


def add_stock(symbol, name=None, sector="輸送用機器", base_price=2800.0, days=30):
    """テスト用の銘柄と価格データを投入する。"""
    if name is None:
        name = f"Test-{symbol}"

    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO stocks (symbol, market, name, sector, currency) "
            "VALUES (?, 'JP', ?, ?, 'JPY')",
            (symbol, name, sector),
        )
        for i in range(days):
            d = (date(2025, 1, 1) + timedelta(days=i)).isoformat()
            close = base_price + i * 5
            conn.execute(
                "INSERT OR IGNORE INTO daily_prices "
                "(symbol, market, date, open, high, low, close, volume) "
                "VALUES (?, 'JP', ?, ?, ?, ?, ?, 500000)",
                (symbol, d, close - 5, close + 15, close - 10, close),
            )
        conn.commit()
