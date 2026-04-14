import pytest

from services.simulation import (
    execute_trade,
    get_account_info,
    get_portfolio_holdings,
    get_trade_stats,
)


class TestBuy:
    def test_buy_success(self, seed_stock):
        result = execute_trade("7203", "JP", "BUY", 10, 2850.0)
        assert result["side"] == "BUY"
        assert result["quantity"] == 10
        assert result["price"] == 2850.0

        info = get_account_info()
        assert info["cash_balance"] == pytest.approx(100000 - 28500)

        holdings = get_portfolio_holdings()
        assert len(holdings) == 1
        assert holdings[0]["symbol"] == "7203"
        assert holdings[0]["quantity"] == 10
        assert holdings[0]["avg_cost"] == pytest.approx(2850.0)

    def test_buy_insufficient_balance(self, seed_stock):
        with pytest.raises(ValueError, match="Insufficient balance"):
            execute_trade("7203", "JP", "BUY", 100, 2850.0)  # 285,000 > 100,000

    def test_buy_unknown_stock(self, test_db):
        with pytest.raises(ValueError, match="not found"):
            execute_trade("9999", "JP", "BUY", 1, 100.0)

    def test_buy_twice_avg_cost(self, seed_stock):
        """2回買いの加重平均取得単価"""
        execute_trade("7203", "JP", "BUY", 10, 2800.0)  # 28,000
        execute_trade("7203", "JP", "BUY", 10, 3000.0)  # 30,000
        # avg = (2800*10 + 3000*10) / 20 = 2900
        holdings = get_portfolio_holdings()
        assert holdings[0]["quantity"] == 20
        assert holdings[0]["avg_cost"] == pytest.approx(2900.0)


class TestSell:
    def test_sell_success(self, seed_stock):
        execute_trade("7203", "JP", "BUY", 10, 2850.0)
        result = execute_trade("7203", "JP", "SELL", 5, 3000.0)
        assert result["side"] == "SELL"
        assert result["quantity"] == 5

        info = get_account_info()
        # 100000 - 28500 + 15000 = 86500
        assert info["cash_balance"] == pytest.approx(86500.0)

        holdings = get_portfolio_holdings()
        assert holdings[0]["quantity"] == 5

    def test_sell_all(self, seed_stock):
        """全売却で保有がなくなる"""
        execute_trade("7203", "JP", "BUY", 10, 2850.0)
        execute_trade("7203", "JP", "SELL", 10, 3000.0)

        holdings = get_portfolio_holdings()
        assert len(holdings) == 0

    def test_sell_insufficient_holdings(self, seed_stock):
        execute_trade("7203", "JP", "BUY", 5, 2850.0)
        with pytest.raises(ValueError, match="Insufficient holdings"):
            execute_trade("7203", "JP", "SELL", 10, 3000.0)

    def test_sell_no_holdings(self, seed_stock):
        with pytest.raises(ValueError, match="Insufficient holdings"):
            execute_trade("7203", "JP", "SELL", 1, 3000.0)


class TestTradeStats:
    def test_no_trades(self, test_db):
        stats = get_trade_stats()
        assert stats["total_trades"] == 0
        assert stats["win_rate"] == 0.0

    def test_win_trade(self, seed_stock):
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        execute_trade("7203", "JP", "SELL", 10, 3000.0)
        stats = get_trade_stats()
        assert stats["total_trades"] == 2
        assert stats["total_realized_pnl"] == pytest.approx(2000.0)  # (3000-2800)*10
        assert stats["win_count"] == 1
        assert stats["win_rate"] == pytest.approx(1.0)

    def test_lose_trade(self, seed_stock):
        execute_trade("7203", "JP", "BUY", 10, 3000.0)
        execute_trade("7203", "JP", "SELL", 10, 2800.0)
        stats = get_trade_stats()
        assert stats["total_realized_pnl"] == pytest.approx(-2000.0)
        assert stats["lose_count"] == 1
        assert stats["win_rate"] == pytest.approx(0.0)


class TestPortfolioHoldings:
    def test_empty(self, test_db):
        holdings = get_portfolio_holdings()
        assert len(holdings) == 0

    def test_with_holdings(self, seed_stock):
        execute_trade("7203", "JP", "BUY", 10, 2850.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 1
        h = holdings[0]
        assert h["symbol"] == "7203"
        assert h["name"] == "トヨタ自動車"
        assert h["quantity"] == 10
        assert h["avg_cost"] == pytest.approx(2850.0)
        # current_price は daily_prices の最新 close (2800+29*10+5 = 3095)
        assert h["current_price"] == pytest.approx(3095.0)
        # unrealized = (3095 - 2850) * 10 = 2450
        assert h["unrealized_pnl"] == pytest.approx(2450.0)


class TestBoundaryBuy:
    """買い注文の境界値テスト"""

    def test_buy_exact_balance(self, seed_stock):
        """残高ぴったりの買い注文 → 残高0"""
        # 100000 / 2500 = 40株
        execute_trade("7203", "JP", "BUY", 40, 2500.0)
        info = get_account_info()
        assert info["cash_balance"] == pytest.approx(0.0)

    def test_buy_one_yen_over_balance(self, seed_stock):
        """残高を1円超える買い注文 → エラー"""
        # 100000 + 1 = 100001
        with pytest.raises(ValueError, match="Insufficient balance"):
            execute_trade("7203", "JP", "BUY", 1, 100001.0)

    def test_buy_quantity_1(self, seed_stock):
        """最小数量1の買い"""
        result = execute_trade("7203", "JP", "BUY", 1, 2850.0)
        assert result["quantity"] == 1
        holdings = get_portfolio_holdings()
        assert holdings[0]["quantity"] == 1

    def test_buy_price_minimum(self, seed_stock):
        """最小価格0.01の買い"""
        result = execute_trade("7203", "JP", "BUY", 1, 0.01)
        assert result["price"] == pytest.approx(0.01)
        info = get_account_info()
        assert info["cash_balance"] == pytest.approx(100000 - 0.01)


class TestBoundarySell:
    """売り注文の境界値テスト"""

    def test_sell_exact_holdings(self, seed_stock):
        """保有数ぴったりの売り注文 → 保有0（行削除）"""
        execute_trade("7203", "JP", "BUY", 10, 2850.0)
        execute_trade("7203", "JP", "SELL", 10, 3000.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 0

    def test_sell_one_over_holdings(self, seed_stock):
        """保有数+1の売り注文 → エラー"""
        execute_trade("7203", "JP", "BUY", 10, 2850.0)
        with pytest.raises(ValueError, match="Insufficient holdings"):
            execute_trade("7203", "JP", "SELL", 11, 3000.0)

    def test_sell_quantity_1(self, seed_stock):
        """最小数量1の売り"""
        execute_trade("7203", "JP", "BUY", 5, 2850.0)
        execute_trade("7203", "JP", "SELL", 1, 3000.0)
        holdings = get_portfolio_holdings()
        assert holdings[0]["quantity"] == 4

    def test_sell_at_same_price(self, seed_stock):
        """買値と同じ価格で売る → 損益0"""
        execute_trade("7203", "JP", "BUY", 10, 2850.0)
        execute_trade("7203", "JP", "SELL", 10, 2850.0)
        stats = get_trade_stats()
        assert stats["total_realized_pnl"] == pytest.approx(0.0)


class TestBoundaryStats:
    """損益統計の境界値テスト"""

    def test_breakeven_trade(self, seed_stock):
        """損益ゼロの取引 → lose扱い（pnl <= 0）"""
        execute_trade("7203", "JP", "BUY", 10, 2850.0)
        execute_trade("7203", "JP", "SELL", 10, 2850.0)
        stats = get_trade_stats()
        assert stats["win_count"] == 0
        assert stats["lose_count"] == 1


class TestValidation:
    def test_invalid_side(self, seed_stock):
        with pytest.raises(ValueError, match="side must be BUY or SELL"):
            execute_trade("7203", "JP", "HOLD", 1, 100.0)

    def test_zero_quantity(self, seed_stock):
        with pytest.raises(ValueError, match="quantity must be positive"):
            execute_trade("7203", "JP", "BUY", 0, 100.0)

    def test_negative_price(self, seed_stock):
        with pytest.raises(ValueError, match="price must be positive"):
            execute_trade("7203", "JP", "BUY", 1, -100.0)
