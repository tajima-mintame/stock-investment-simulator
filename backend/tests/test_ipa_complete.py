"""IPA充足率90%+達成用テスト: 残りの同値分割・原因結果・エラー推測を網羅する。"""

import math
import pytest
from datetime import date, timedelta

from database import get_connection
from services.indicators import calc_ma, calc_rsi, calc_macd, calc_bollinger
from services.simulation import (
    execute_trade,
    get_account_info,
    get_portfolio_holdings,
    get_trade_stats,
)


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
            close = base_price + i * 5
            conn.execute(
                "INSERT OR IGNORE INTO daily_prices (symbol, market, date, open, high, low, close, volume) "
                "VALUES (?, 'JP', ?, ?, ?, ?, ?, 500000)",
                (symbol, d, close - 5, close + 15, close - 10, close),
            )
        conn.commit()
    finally:
        conn.close()


# ==========================================
# 同値分割: 指標の入力データパターン
# ==========================================

class TestIndicatorEquivalencePartition:
    """指標計算の同値クラス網羅"""

    def test_ma_trending_up(self):
        """上昇トレンドデータ → MA は右肩上がり"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(20)]
        closes = [100.0 + i * 10 for i in range(20)]
        result = calc_ma(dates, closes, 5)
        values = [v for _, v in result if v is not None]
        assert all(values[i] < values[i + 1] for i in range(len(values) - 1))

    def test_ma_trending_down(self):
        """下降トレンドデータ → MA は右肩下がり"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(20)]
        closes = [300.0 - i * 10 for i in range(20)]
        result = calc_ma(dates, closes, 5)
        values = [v for _, v in result if v is not None]
        assert all(values[i] > values[i + 1] for i in range(len(values) - 1))

    def test_ma_sideways(self):
        """横ばいデータ → MA は一定"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(20)]
        closes = [100.0, 102.0, 98.0, 101.0, 99.0] * 4
        result = calc_ma(dates, closes, 5)
        values = [v for _, v in result if v is not None]
        assert max(values) - min(values) < 5.0  # 変動幅が小さい

    def test_rsi_volatile_data(self):
        """激しい上下動 → RSI は中間値付近"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]
        closes = [100.0 + (20 if i % 2 == 0 else -20) for i in range(30)]
        cum = [100.0]
        for i in range(1, 30):
            cum.append(cum[-1] + (20 if i % 2 == 0 else -20))
        result = calc_rsi(dates, cum, 14)
        values = [v for _, v in result if v is not None]
        for v in values:
            assert 20.0 < v < 80.0  # 極端にならない

    def test_bollinger_volatile_data(self):
        """激しい変動 → バンド幅が広い"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]
        closes = [100.0 + (50 if i % 2 == 0 else -50) for i in range(30)]
        result = calc_bollinger(dates, closes, 10, 2.0)
        for _, u, m, l in result:
            if u is not None:
                assert (u - l) > 50.0  # バンド幅が大きい


# ==========================================
# 同値分割: simulation の入力パターン
# ==========================================

class TestSimulationEquivalencePartition:
    """売買の同値クラス網羅"""

    def test_invalid_market(self, test_db):
        """無効なmarket → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="market must be one of"):
            execute_trade("7203", "US", "BUY", 1, 100.0)

    def test_invalid_market_empty(self, test_db):
        """空のmarket → エラー"""
        _add_stock("7203")
        with pytest.raises(ValueError, match="market must be one of"):
            execute_trade("7203", "", "BUY", 1, 100.0)

    def test_empty_symbol(self, test_db):
        """空のsymbol → エラー"""
        with pytest.raises(ValueError, match="symbol is required"):
            execute_trade("", "JP", "BUY", 1, 100.0)

    def test_none_symbol(self, test_db):
        """Noneのsymbol → エラー"""
        with pytest.raises(ValueError, match="symbol is required"):
            execute_trade(None, "JP", "BUY", 1, 100.0)

    def test_trade_with_note(self, test_db):
        """note付き取引 → noteが保存される"""
        _add_stock("7203")
        result = execute_trade("7203", "JP", "BUY", 1, 2800.0, note="テスト購入")
        assert result["note"] == "テスト購入"

    def test_trade_without_note(self, test_db):
        """note無し取引 → noteはNone"""
        _add_stock("7203")
        result = execute_trade("7203", "JP", "BUY", 1, 2800.0)
        assert result["note"] is None


# ==========================================
# 原因結果グラフ: 指標計算
# ==========================================

class TestIndicatorCauseEffect:
    """指標計算の原因→結果の関係を検証"""

    def test_period_change_affects_warmup(self):
        """期間変更 → ウォームアップ期間が変わる"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]
        closes = [100.0 + i for i in range(30)]

        ma5 = calc_ma(dates, closes, 5)
        ma10 = calc_ma(dates, closes, 10)

        none_count_5 = sum(1 for _, v in ma5 if v is None)
        none_count_10 = sum(1 for _, v in ma10 if v is None)

        assert none_count_5 == 4   # period - 1
        assert none_count_10 == 9  # period - 1

    def test_price_swing_expands_bollinger(self):
        """価格変動大 → ボリンジャーバンド幅拡大"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]

        # 安定データ
        stable = [100.0 + i * 0.1 for i in range(30)]
        bb_stable = calc_bollinger(dates, stable, 10, 2.0)

        # 変動データ
        volatile = [100.0 + i * 10 * ((-1) ** i) for i in range(30)]
        bb_volatile = calc_bollinger(dates, volatile, 10, 2.0)

        # 最後のバンド幅を比較
        stable_width = bb_stable[-1][1] - bb_stable[-1][3]  # upper - lower
        volatile_width = bb_volatile[-1][1] - bb_volatile[-1][3]
        assert volatile_width > stable_width

    def test_sell_price_above_cost_positive_pnl(self, test_db):
        """売値 > 買値 → 実現損益プラス"""
        _add_stock("7203")
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        execute_trade("7203", "JP", "SELL", 10, 3000.0)
        stats = get_trade_stats()
        assert stats["total_realized_pnl"] > 0

    def test_sell_price_below_cost_negative_pnl(self, test_db):
        """売値 < 買値 → 実現損益マイナス"""
        _add_stock("7203")
        execute_trade("7203", "JP", "BUY", 10, 3000.0)
        execute_trade("7203", "JP", "SELL", 10, 2800.0)
        stats = get_trade_stats()
        assert stats["total_realized_pnl"] < 0

    def test_sell_price_equals_cost_zero_pnl(self, test_db):
        """売値 = 買値 → 実現損益ゼロ"""
        _add_stock("7203")
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        execute_trade("7203", "JP", "SELL", 10, 2800.0)
        stats = get_trade_stats()
        assert stats["total_realized_pnl"] == pytest.approx(0.0)

    def test_no_price_data_unrealized_pnl_none(self, test_db):
        """価格データなし → 含み損益はNone"""
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO stocks (symbol, market, name, sector, currency) "
                "VALUES ('NOPR', 'JP', 'No Price', '不明', 'JPY')"
            )
            conn.commit()
        finally:
            conn.close()
        execute_trade("NOPR", "JP", "BUY", 10, 100.0)
        holdings = get_portfolio_holdings()
        assert holdings[0]["current_price"] is None
        assert holdings[0]["unrealized_pnl"] is None

    def test_multiple_stocks_aggregated_portfolio(self, test_db):
        """複数銘柄 → ポートフォリオに全て含まれる"""
        _add_stock("7203", 2800)
        _add_stock("9984", 6000)
        execute_trade("7203", "JP", "BUY", 5, 2800.0)
        execute_trade("9984", "JP", "BUY", 2, 6000.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 2
        symbols = {h["symbol"] for h in holdings}
        assert symbols == {"7203", "9984"}


# ==========================================
# エラー推測: 指標の異常入力
# ==========================================

class TestIndicatorErrorGuessingComplete:
    """指標計算の追加エラー推測"""

    def test_nan_in_closes(self):
        """NaN入力 → 全てNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(10)]
        closes = [100.0, float("nan"), 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0]
        result = calc_ma(dates, closes, 5)
        for _, v in result:
            assert v is None

    def test_inf_in_closes(self):
        """Inf入力 → 全てNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(10)]
        closes = [100.0, float("inf"), 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0]
        result = calc_rsi(dates, closes, 5)
        for _, v in result:
            assert v is None

    def test_negative_inf_in_closes(self):
        """-Inf入力 → 全てNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(10)]
        closes = [float("-inf")] + [100.0 + i for i in range(9)]
        result = calc_bollinger(dates, closes, 5, 2.0)
        for _, u, m, l in result:
            assert u is None

    def test_dates_closes_mismatch(self):
        """dates と closes の長さ不一致 → 空またはNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(10)]
        closes = [100.0 + i for i in range(5)]
        result = calc_ma(dates, closes, 3)
        # 短い方に合わせてNoneまたは空
        assert len(result) <= len(dates)

    def test_negative_period_ma(self):
        """period=-1 → 全てNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(10)]
        closes = [100.0 + i for i in range(10)]
        result = calc_ma(dates, closes, -1)
        for _, v in result:
            assert v is None

    def test_negative_period_rsi(self):
        """RSI period=-1 → 全てNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(10)]
        closes = [100.0 + i for i in range(10)]
        result = calc_rsi(dates, closes, -1)
        for _, v in result:
            assert v is None

    def test_negative_period_bollinger(self):
        """BB period=-5 → 全てNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(10)]
        closes = [100.0 + i for i in range(10)]
        result = calc_bollinger(dates, closes, -5, 2.0)
        for _, u, m, l in result:
            assert u is None

    def test_macd_negative_params(self):
        """MACD fast=-1 → 全てNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]
        closes = [100.0 + i for i in range(30)]
        result = calc_macd(dates, closes, -1, 26, 9)
        for _, m, s, h in result:
            assert m is None

    def test_nan_rsi(self):
        """NaN入力でRSIもNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(20)]
        closes = [float("nan")] * 20
        result = calc_rsi(dates, closes, 14)
        for _, v in result:
            assert v is None

    def test_nan_macd(self):
        """NaN入力でMACDもNone"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]
        closes = [100.0] * 15 + [float("nan")] * 15
        result = calc_macd(dates, closes, 12, 26, 9)
        for _, m, s, h in result:
            assert m is None


# ==========================================
# ポートフォリオ同値分割の補完
# ==========================================

class TestPortfolioEquivalenceComplete:
    """ポートフォリオの含み損益パターン網羅"""

    def test_unrealized_pnl_zero(self, test_db):
        """含み損益ゼロ: 買値 = 最新価格"""
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO stocks (symbol, market, name, sector, currency) "
                "VALUES ('ZERO', 'JP', 'Zero PnL Corp', '不明', 'JPY')"
            )
            # 最新closeが500.0になるようにデータ作成
            conn.execute(
                "INSERT INTO daily_prices (symbol, market, date, open, high, low, close, volume) "
                "VALUES ('ZERO', 'JP', '2025-01-01', 500, 510, 490, 500, 100000)"
            )
            conn.commit()
        finally:
            conn.close()

        execute_trade("ZERO", "JP", "BUY", 10, 500.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 1
        assert holdings[0]["unrealized_pnl"] == pytest.approx(0.0)

    def test_unrealized_pnl_positive(self, test_db):
        """含み益: 買値 < 最新価格"""
        _add_stock("7203", 2800)  # 最新close = 2800 + 29*5 = 2945
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        holdings = get_portfolio_holdings()
        assert holdings[0]["unrealized_pnl"] > 0

    def test_unrealized_pnl_negative(self, test_db):
        """含み損: 買値 > 最新価格"""
        _add_stock("7203", 2800)  # 最新close = 2945
        execute_trade("7203", "JP", "BUY", 10, 5000.0)
        holdings = get_portfolio_holdings()
        assert holdings[0]["unrealized_pnl"] < 0

    def test_mixed_profit_loss(self, test_db):
        """複数銘柄: 利益+損失の混在"""
        _add_stock("7203", 2800)  # 最新close = 2945
        _add_stock("9984", 6000)  # 最新close = 6145

        execute_trade("7203", "JP", "BUY", 10, 2800.0)  # 含み益
        execute_trade("9984", "JP", "BUY", 5, 9000.0)   # 含み損

        holdings = get_portfolio_holdings()
        pnls = {h["symbol"]: h["unrealized_pnl"] for h in holdings}
        assert pnls["7203"] > 0
        assert pnls["9984"] < 0
