"""回帰テスト: 機能を跨いだEnd-to-Endシナリオで既存機能の整合性を検証する。"""

import pytest
from datetime import date, timedelta

from database import get_connection
from services.simulation import (
    execute_trade,
    get_account_info,
    get_portfolio_holdings,
    get_trade_stats,
)
from services.indicators import calc_ma, calc_rsi, calc_macd, calc_bollinger


def _seed_multiple_stocks(test_db):
    """複数銘柄のテストデータを投入する。"""
    conn = get_connection()
    try:
        stocks = [
            ("7203", "トヨタ自動車", "輸送用機器", 2800.0),
            ("9984", "ソフトバンクG", "情報・通信業", 6000.0),
            ("6758", "ソニーG", "電気機器", 3200.0),
        ]
        for symbol, name, sector, base_price in stocks:
            conn.execute(
                "INSERT INTO stocks (symbol, market, name, sector, currency) "
                "VALUES (?, 'JP', ?, ?, 'JPY')",
                (symbol, name, sector),
            )
            for i in range(60):
                d = (date(2025, 1, 1) + timedelta(days=i)).isoformat()
                # 各銘柄で異なる値動き
                close = base_price + i * 5 + ((-1) ** i) * 10
                conn.execute(
                    "INSERT INTO daily_prices (symbol, market, date, open, high, low, close, volume) "
                    "VALUES (?, 'JP', ?, ?, ?, ?, ?, ?)",
                    (symbol, d, close - 5, close + 15, close - 15, close, 500000 + i * 1000),
                )
        conn.commit()
    finally:
        conn.close()


class TestFullTradeLifecycle:
    """データ同期→指標計算→売買→損益確認の一連のフロー"""

    def test_single_stock_lifecycle(self, seed_stock):
        """1銘柄: 指標確認 → 買い → 含み損益確認 → 売り → 損益確認"""
        # 1. 指標を計算（データが存在することの確認）
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT date, close FROM daily_prices WHERE symbol='7203' AND market='JP' ORDER BY date"
            ).fetchall()
        finally:
            conn.close()

        dates = [date.fromisoformat(r["date"]) for r in rows]
        closes = [r["close"] for r in rows]
        assert len(dates) == 30

        ma = calc_ma(dates, closes, 5)
        rsi = calc_rsi(dates, closes, 14)
        assert any(v is not None for _, v in ma)
        assert any(v is not None for _, v in rsi)

        # 2. 買い注文
        initial = get_account_info()
        assert initial["cash_balance"] == pytest.approx(100000.0)

        execute_trade("7203", "JP", "BUY", 10, 2850.0)

        # 3. 含み損益確認
        holdings = get_portfolio_holdings()
        assert len(holdings) == 1
        assert holdings[0]["quantity"] == 10
        assert holdings[0]["unrealized_pnl"] is not None

        account_after_buy = get_account_info()
        assert account_after_buy["cash_balance"] == pytest.approx(100000 - 28500)
        assert account_after_buy["portfolio_value"] > 0
        # total = cash + portfolio
        assert account_after_buy["total_value"] == pytest.approx(
            account_after_buy["cash_balance"] + account_after_buy["portfolio_value"]
        )

        # 4. 売り注文
        execute_trade("7203", "JP", "SELL", 10, 3000.0)

        # 5. 損益確認
        holdings_after = get_portfolio_holdings()
        assert len(holdings_after) == 0

        stats = get_trade_stats()
        assert stats["total_trades"] == 2
        assert stats["total_realized_pnl"] == pytest.approx(1500.0)  # (3000-2850)*10
        assert stats["win_count"] == 1
        assert stats["win_rate"] == pytest.approx(1.0)

        # 6. 残高整合性: 初期残高 + 実現損益 = 最終残高
        final = get_account_info()
        assert final["cash_balance"] == pytest.approx(100000.0 + 1500.0)
        assert final["portfolio_value"] == pytest.approx(0.0)


class TestMultiStockPortfolio:
    """複数銘柄でのポートフォリオ整合性"""

    def test_multi_stock_buy_sell(self, test_db):
        _seed_multiple_stocks(test_db)

        initial = get_account_info()
        initial_cash = initial["cash_balance"]

        # 3銘柄を買う
        execute_trade("7203", "JP", "BUY", 5, 2800.0)   # 14,000
        execute_trade("9984", "JP", "BUY", 2, 6000.0)   # 12,000
        execute_trade("6758", "JP", "BUY", 3, 3200.0)   #  9,600
        total_spent = 14000 + 12000 + 9600

        # 残高確認
        info = get_account_info()
        assert info["cash_balance"] == pytest.approx(initial_cash - total_spent)

        # 保有確認
        holdings = get_portfolio_holdings()
        assert len(holdings) == 3
        symbols = {h["symbol"] for h in holdings}
        assert symbols == {"7203", "9984", "6758"}

        # ポートフォリオ時価総額 = Σ(数量 × 最新終値) > 0
        assert info["portfolio_value"] > 0
        assert info["total_value"] == pytest.approx(
            info["cash_balance"] + info["portfolio_value"]
        )

        # 1銘柄だけ売る
        execute_trade("9984", "JP", "SELL", 2, 6500.0)  # 13,000

        holdings_after = get_portfolio_holdings()
        assert len(holdings_after) == 2
        remaining_symbols = {h["symbol"] for h in holdings_after}
        assert "9984" not in remaining_symbols

        # 損益確認
        stats = get_trade_stats()
        assert stats["total_realized_pnl"] == pytest.approx(1000.0)  # (6500-6000)*2

    def test_portfolio_total_consistency(self, test_db):
        """total_value = cash + portfolio_value が常に成立する"""
        _seed_multiple_stocks(test_db)

        # 各操作後にtotal整合性を確認
        for symbol, qty, price in [("7203", 5, 2800), ("9984", 2, 6000)]:
            execute_trade(symbol, "JP", "BUY", qty, float(price))
            info = get_account_info()
            assert info["total_value"] == pytest.approx(
                info["cash_balance"] + info["portfolio_value"]
            )

        execute_trade("7203", "JP", "SELL", 3, 3000.0)
        info = get_account_info()
        assert info["total_value"] == pytest.approx(
            info["cash_balance"] + info["portfolio_value"]
        )


class TestIndicatorsAfterTrade:
    """取引後も指標計算に影響がないことを確認"""

    def test_indicators_unchanged_by_trade(self, seed_stock):
        # 取引前の指標
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT date, close FROM daily_prices WHERE symbol='7203' AND market='JP' ORDER BY date"
            ).fetchall()
        finally:
            conn.close()

        dates = [date.fromisoformat(r["date"]) for r in rows]
        closes = [r["close"] for r in rows]

        ma_before = calc_ma(dates, closes, 5)
        rsi_before = calc_rsi(dates, closes, 14)
        bb_before = calc_bollinger(dates, closes, 20, 2.0)

        # 取引実行
        execute_trade("7203", "JP", "BUY", 5, 2850.0)
        execute_trade("7203", "JP", "SELL", 5, 3000.0)

        # 取引後の指標（同じデータなので同じ結果のはず）
        ma_after = calc_ma(dates, closes, 5)
        rsi_after = calc_rsi(dates, closes, 14)
        bb_after = calc_bollinger(dates, closes, 20, 2.0)

        for i in range(len(ma_before)):
            assert ma_before[i][1] == ma_after[i][1]
        for i in range(len(rsi_before)):
            assert rsi_before[i][1] == rsi_after[i][1]
        for i in range(len(bb_before)):
            assert bb_before[i][1] == bb_after[i][1]


class TestCashFlowIntegrity:
    """全取引を通じた残高の整合性"""

    def test_cash_flow_matches_trades(self, seed_stock):
        """最終残高 = 初期残高 - Σ(BUY額) + Σ(SELL額)"""
        initial = get_account_info()["cash_balance"]

        trades = [
            ("BUY", 10, 2800.0),
            ("BUY", 5, 2900.0),
            ("SELL", 8, 3000.0),
            ("SELL", 3, 2850.0),
        ]

        expected_cash = initial
        for side, qty, price in trades:
            execute_trade("7203", "JP", side, qty, price)
            if side == "BUY":
                expected_cash -= qty * price
            else:
                expected_cash += qty * price

        actual = get_account_info()["cash_balance"]
        assert actual == pytest.approx(expected_cash)

    def test_fifo_pnl_with_multiple_lots(self, seed_stock):
        """複数ロットのFIFO損益計算の正確性"""
        # Lot 1: 10 @ 2800
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        # Lot 2: 10 @ 3000
        execute_trade("7203", "JP", "BUY", 10, 3000.0)

        # 15株を3100で売却 → FIFO: Lot1の10株(+300*10=3000) + Lot2の5株(+100*5=500)
        execute_trade("7203", "JP", "SELL", 15, 3100.0)

        stats = get_trade_stats()
        assert stats["total_realized_pnl"] == pytest.approx(3500.0)

        # 残り5株はLot2の残り(avg_cost=3000)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 1
        assert holdings[0]["quantity"] == 5
