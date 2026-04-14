"""状態遷移テスト: ポートフォリオ・口座・保有の状態遷移を検証する。"""

import pytest
from datetime import date, timedelta

from database import get_connection
from services.simulation import (
    execute_trade,
    get_account_info,
    get_portfolio_holdings,
    get_trade_stats,
)


def _add_stock(symbol, name, sector, base_price, days=30):
    """テスト用銘柄と価格データを追加する。"""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO stocks (symbol, market, name, sector, currency) "
            "VALUES (?, 'JP', ?, ?, 'JPY')",
            (symbol, name, sector),
        )
        for i in range(days):
            d = (date(2025, 1, 1) + timedelta(days=i)).isoformat()
            close = base_price + i * 5
            conn.execute(
                "INSERT OR IGNORE INTO daily_prices (symbol, market, date, open, high, low, close, volume) "
                "VALUES (?, 'JP', ?, ?, ?, ?, ?, ?)",
                (symbol, d, close - 5, close + 15, close - 10, close, 500000),
            )
        conn.commit()
    finally:
        conn.close()


class TestPortfolioStateTransition:
    """ポートフォリオ状態: 空 → 1銘柄 → 2銘柄 → 部分売却 → 全売却 → 空"""

    def test_full_lifecycle(self, test_db):
        _add_stock("7203", "トヨタ", "輸送用機器", 2800)
        _add_stock("9984", "ソフトバンクG", "情報・通信業", 6000)

        # 状態1: 空
        holdings = get_portfolio_holdings()
        assert len(holdings) == 0

        # 状態2: 1銘柄保有
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 1
        assert holdings[0]["symbol"] == "7203"

        # 状態3: 2銘柄保有
        execute_trade("9984", "JP", "BUY", 5, 6000.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 2
        symbols = {h["symbol"] for h in holdings}
        assert symbols == {"7203", "9984"}

        # 状態4: 1銘柄を部分売却 → まだ2銘柄
        execute_trade("7203", "JP", "SELL", 5, 3000.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 2
        toyota = next(h for h in holdings if h["symbol"] == "7203")
        assert toyota["quantity"] == 5

        # 状態5: 1銘柄を全売却 → 1銘柄
        execute_trade("7203", "JP", "SELL", 5, 3100.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 1
        assert holdings[0]["symbol"] == "9984"

        # 状態6: 残りも全売却 → 空
        execute_trade("9984", "JP", "SELL", 5, 6500.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 0


class TestAccountBalanceTransition:
    """口座残高状態: 初期 → 買い減算 → 買い減算 → 売り加算 → 全売却復帰"""

    def test_balance_through_operations(self, test_db):
        _add_stock("7203", "トヨタ", "輸送用機器", 2800)

        initial = get_account_info()["cash_balance"]
        assert initial == pytest.approx(100000.0)

        # BUY 1: 10 @ 2800 = 28000
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        balance1 = get_account_info()["cash_balance"]
        assert balance1 == pytest.approx(initial - 28000)

        # BUY 2: 5 @ 3000 = 15000
        execute_trade("7203", "JP", "BUY", 5, 3000.0)
        balance2 = get_account_info()["cash_balance"]
        assert balance2 == pytest.approx(balance1 - 15000)

        # SELL: 10 @ 3200 = 32000
        execute_trade("7203", "JP", "SELL", 10, 3200.0)
        balance3 = get_account_info()["cash_balance"]
        assert balance3 == pytest.approx(balance2 + 32000)

        # SELL ALL: 5 @ 3100 = 15500
        execute_trade("7203", "JP", "SELL", 5, 3100.0)
        balance_final = get_account_info()["cash_balance"]
        assert balance_final == pytest.approx(balance3 + 15500)

        # 最終残高 = 初期 - 28000 - 15000 + 32000 + 15500 = 104500
        assert balance_final == pytest.approx(104500.0)
        assert get_account_info()["portfolio_value"] == pytest.approx(0.0)


class TestTradeStatsTransition:
    """損益統計状態: 0件 → 買いのみ → 勝ち売り → 負け売り → 混合"""

    def test_stats_progression(self, test_db):
        _add_stock("7203", "トヨタ", "輸送用機器", 2800)

        # 状態1: 取引なし
        stats = get_trade_stats()
        assert stats["total_trades"] == 0
        assert stats["total_realized_pnl"] == pytest.approx(0.0)

        # 状態2: 買いのみ（まだ実現損益なし）
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        stats = get_trade_stats()
        assert stats["total_trades"] == 1
        assert stats["total_realized_pnl"] == pytest.approx(0.0)

        # 状態3: 勝ち売り
        execute_trade("7203", "JP", "SELL", 5, 3000.0)
        stats = get_trade_stats()
        assert stats["total_trades"] == 2
        assert stats["total_realized_pnl"] == pytest.approx(1000.0)  # (3000-2800)*5
        assert stats["win_count"] == 1
        assert stats["lose_count"] == 0

        # 状態4: 追加購入 + 負け売り
        execute_trade("7203", "JP", "BUY", 10, 3200.0)
        execute_trade("7203", "JP", "SELL", 10, 2900.0)
        stats = get_trade_stats()
        assert stats["total_trades"] == 4
        # 2回目の売り: FIFO → 残りLot1の5株@2800(+100*5=500) + Lot2の5株@3200(-300*5=-1500) = -1000
        assert stats["win_count"] == 1
        assert stats["lose_count"] == 1


class TestHoldingCountTransition:
    """保有銘柄数の遷移: 0 → 1 → 2 → 3 → 2 → 1 → 0"""

    def test_holding_count_sequence(self, test_db):
        _add_stock("7203", "トヨタ", "輸送用機器", 2800)
        _add_stock("9984", "ソフトバンクG", "情報・通信業", 6000)
        _add_stock("6758", "ソニーG", "電気機器", 3200)

        assert len(get_portfolio_holdings()) == 0

        execute_trade("7203", "JP", "BUY", 5, 2800.0)
        assert len(get_portfolio_holdings()) == 1

        execute_trade("9984", "JP", "BUY", 2, 6000.0)
        assert len(get_portfolio_holdings()) == 2

        execute_trade("6758", "JP", "BUY", 3, 3200.0)
        assert len(get_portfolio_holdings()) == 3

        execute_trade("9984", "JP", "SELL", 2, 6500.0)
        assert len(get_portfolio_holdings()) == 2

        execute_trade("6758", "JP", "SELL", 3, 3500.0)
        assert len(get_portfolio_holdings()) == 1

        execute_trade("7203", "JP", "SELL", 5, 3000.0)
        assert len(get_portfolio_holdings()) == 0


class TestTotalValueInvariant:
    """total_value = cash + portfolio_value が全操作で成立する不変条件"""

    def test_invariant_through_all_operations(self, test_db):
        _add_stock("7203", "トヨタ", "輸送用機器", 2800)
        _add_stock("9984", "ソフトバンクG", "情報・通信業", 6000)

        def assert_total_invariant():
            info = get_account_info()
            assert info["total_value"] == pytest.approx(
                info["cash_balance"] + info["portfolio_value"]
            )

        assert_total_invariant()

        for symbol, qty, price in [
            ("7203", 5, 2800.0),
            ("9984", 2, 6000.0),
            ("7203", 3, 2900.0),
        ]:
            execute_trade(symbol, "JP", "BUY", qty, price)
            assert_total_invariant()

        for symbol, qty, price in [
            ("7203", 4, 3000.0),
            ("9984", 1, 6200.0),
        ]:
            execute_trade(symbol, "JP", "SELL", qty, price)
            assert_total_invariant()
