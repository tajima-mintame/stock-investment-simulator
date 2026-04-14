"""デシジョンテーブルテスト: 条件の組み合わせを網羅的に検証する。"""

import pytest
from datetime import date, timedelta

from database import get_connection
from services.simulation import execute_trade, get_account_info, get_portfolio_holdings


def _add_stock(symbol, base_price=2800.0, days=30):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO stocks (symbol, market, name, sector, currency) "
            "VALUES (?, 'JP', ?, '輸送用機器', 'JPY')",
            (symbol, f"Test-{symbol}"),
        )
        for i in range(days):
            d = (date(2025, 1, 1) + timedelta(days=i)).isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO daily_prices (symbol, market, date, open, high, low, close, volume) "
                "VALUES (?, 'JP', ?, ?, ?, ?, ?, 500000)",
                (symbol, d, base_price, base_price + 10, base_price - 10, base_price + i),
            )
        conn.commit()
    finally:
        conn.close()


class TestExecuteTradeDecisionTable:
    """
    execute_trade のデシジョンテーブル:
    条件: [銘柄存在] × [BUY/SELL] × [数量有効] × [価格有効] × [残高/保有充足]
    """

    # --- 正常系: 全条件OK ---

    def test_valid_buy_sufficient_balance(self, test_db):
        """銘柄○ × BUY × 数量○ × 価格○ × 残高○ → 成功"""
        _add_stock("7203")
        result = execute_trade("7203", "JP", "BUY", 10, 2800.0)
        assert result["side"] == "BUY"

    def test_valid_sell_sufficient_holdings(self, test_db):
        """銘柄○ × SELL × 数量○ × 価格○ × 保有○ → 成功"""
        _add_stock("7203")
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        result = execute_trade("7203", "JP", "SELL", 5, 3000.0)
        assert result["side"] == "SELL"

    # --- 銘柄なし ---

    def test_invalid_stock_buy(self, test_db):
        """銘柄× × BUY → エラー"""
        with pytest.raises(ValueError, match="not found"):
            execute_trade("9999", "JP", "BUY", 1, 100.0)

    def test_invalid_stock_sell(self, test_db):
        """銘柄× × SELL → エラー"""
        with pytest.raises(ValueError, match="not found"):
            execute_trade("9999", "JP", "SELL", 1, 100.0)

    # --- 残高/保有不足 ---

    def test_buy_insufficient_balance(self, test_db):
        """銘柄○ × BUY × 残高× → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="Insufficient balance"):
            execute_trade("7203", "JP", "BUY", 100, 2800.0)  # 280,000 > 100,000

    def test_sell_insufficient_holdings(self, test_db):
        """銘柄○ × SELL × 保有× → エラー"""
        _add_stock("7203")
        execute_trade("7203", "JP", "BUY", 5, 2800.0)
        with pytest.raises(ValueError, match="Insufficient holdings"):
            execute_trade("7203", "JP", "SELL", 10, 3000.0)

    def test_sell_no_holdings(self, test_db):
        """銘柄○ × SELL × 保有0 → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="Insufficient holdings"):
            execute_trade("7203", "JP", "SELL", 1, 3000.0)

    # --- 数量/価格不正 ---

    def test_buy_zero_quantity(self, test_db):
        """銘柄○ × BUY × 数量0 → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="quantity must be positive"):
            execute_trade("7203", "JP", "BUY", 0, 2800.0)

    def test_buy_negative_quantity(self, test_db):
        """銘柄○ × BUY × 数量負 → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="quantity must be positive"):
            execute_trade("7203", "JP", "BUY", -1, 2800.0)

    def test_sell_zero_quantity(self, test_db):
        """銘柄○ × SELL × 数量0 → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="quantity must be positive"):
            execute_trade("7203", "JP", "SELL", 0, 3000.0)

    def test_buy_zero_price(self, test_db):
        """銘柄○ × BUY × 価格0 → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="price must be positive"):
            execute_trade("7203", "JP", "BUY", 1, 0.0)

    def test_buy_negative_price(self, test_db):
        """銘柄○ × BUY × 価格負 → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="price must be positive"):
            execute_trade("7203", "JP", "BUY", 1, -100.0)

    # --- side 不正 ---

    def test_invalid_side(self, test_db):
        """銘柄○ × 不正side → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="side must be BUY or SELL"):
            execute_trade("7203", "JP", "HOLD", 1, 100.0)

    def test_empty_side(self, test_db):
        """銘柄○ × 空side → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="side must be BUY or SELL"):
            execute_trade("7203", "JP", "", 1, 100.0)


class TestStocksFilterDecisionTable:
    """
    GET /api/stocks のフィルタ組み合わせ:
    条件: [market] × [sector] × [q]
    """

    def _seed_stocks(self):
        conn = get_connection()
        try:
            stocks = [
                ("7203", "JP", "トヨタ自動車", "輸送用機器"),
                ("9984", "JP", "ソフトバンクG", "情報・通信業"),
                ("6758", "JP", "ソニーG", "電気機器"),
            ]
            for sym, mkt, name, sector in stocks:
                conn.execute(
                    "INSERT OR IGNORE INTO stocks (symbol, market, name, sector, currency) "
                    "VALUES (?, ?, ?, ?, 'JPY')",
                    (sym, mkt, name, sector),
                )
            conn.commit()
        finally:
            conn.close()

    def test_no_filters(self, app_client, test_db):
        """フィルタなし → 全件"""
        self._seed_stocks()
        resp = app_client.get("/api/stocks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    def test_market_filter(self, app_client, test_db):
        """market=JP → JP銘柄のみ"""
        self._seed_stocks()
        resp = app_client.get("/api/stocks?market=JP")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    def test_sector_filter(self, app_client, test_db):
        """sector=電気機器 → 1件"""
        self._seed_stocks()
        resp = app_client.get("/api/stocks?sector=電気機器")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["stocks"][0]["symbol"] == "6758"

    def test_q_filter(self, app_client, test_db):
        """q=トヨタ → 1件"""
        self._seed_stocks()
        resp = app_client.get("/api/stocks?q=トヨタ")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_market_and_sector(self, app_client, test_db):
        """market=JP & sector=情報・通信業 → 1件"""
        self._seed_stocks()
        resp = app_client.get("/api/stocks?market=JP&sector=情報・通信業")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["stocks"][0]["symbol"] == "9984"

    def test_q_and_sector(self, app_client, test_db):
        """q=ソニー & sector=電気機器 → 1件"""
        self._seed_stocks()
        resp = app_client.get("/api/stocks?q=ソニー&sector=電気機器")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_no_match(self, app_client, test_db):
        """存在しない条件 → 0件"""
        self._seed_stocks()
        resp = app_client.get("/api/stocks?sector=食品")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_q_partial_match(self, app_client, test_db):
        """q=ソフト → 部分一致で1件"""
        self._seed_stocks()
        resp = app_client.get("/api/stocks?q=ソフト")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


class TestIndicatorTypeDecisionTable:
    """
    指標リクエストの type パラメータ組み合わせ
    """

    def test_ma_only(self, app_client, seed_stock):
        resp = app_client.get("/api/stocks/JP/7203/indicators?type=ma")
        data = resp.json()
        assert data["ma"] is not None
        assert data["rsi"] is None
        assert data["macd"] is None
        assert data["bollinger"] is None

    def test_rsi_only(self, app_client, seed_stock):
        resp = app_client.get("/api/stocks/JP/7203/indicators?type=rsi")
        data = resp.json()
        assert data["ma"] is None
        assert data["rsi"] is not None

    def test_macd_only(self, app_client, seed_stock):
        resp = app_client.get("/api/stocks/JP/7203/indicators?type=macd")
        data = resp.json()
        assert data["macd"] is not None
        assert data["ma"] is None

    def test_bb_only(self, app_client, seed_stock):
        resp = app_client.get("/api/stocks/JP/7203/indicators?type=bb")
        data = resp.json()
        assert data["bollinger"] is not None
        assert data["ma"] is None

    def test_ma_and_rsi(self, app_client, seed_stock):
        resp = app_client.get("/api/stocks/JP/7203/indicators?type=ma,rsi")
        data = resp.json()
        assert data["ma"] is not None
        assert data["rsi"] is not None
        assert data["macd"] is None

    def test_all_types(self, app_client, seed_stock):
        resp = app_client.get("/api/stocks/JP/7203/indicators?type=ma,rsi,macd,bb")
        data = resp.json()
        assert data["ma"] is not None
        assert data["rsi"] is not None
        assert data["macd"] is not None
        assert data["bollinger"] is not None

    def test_unknown_type_ignored(self, app_client, seed_stock):
        """未知のタイプは無視される"""
        resp = app_client.get("/api/stocks/JP/7203/indicators?type=unknown")
        data = resp.json()
        assert data["ma"] is None
        assert data["rsi"] is None
