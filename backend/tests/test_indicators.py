import math
from datetime import date, timedelta

from services.indicators import calc_bollinger, calc_ma, calc_macd, calc_rsi


def _make_data(n, start_price=100.0, step=1.0):
    """テスト用の日付と終値を生成する。"""
    start = date(2025, 1, 1)
    dates = [start + timedelta(days=i) for i in range(n)]
    closes = [start_price + i * step for i in range(n)]
    return dates, closes


class TestCalcMA:
    def test_basic(self):
        dates, closes = _make_data(10)
        result = calc_ma(dates, closes, 5)
        assert len(result) == 10
        # 最初の4つはNone（ウォームアップ）
        for i in range(4):
            assert result[i][1] is None
        # index=4: avg(100,101,102,103,104) = 102.0
        assert result[4][1] == pytest.approx(102.0)
        # index=9: avg(105,106,107,108,109) = 107.0
        assert result[9][1] == pytest.approx(107.0)

    def test_period_1(self):
        dates, closes = _make_data(5)
        result = calc_ma(dates, closes, 1)
        for i in range(5):
            assert result[i][1] == pytest.approx(closes[i])

    def test_insufficient_data(self):
        dates, closes = _make_data(3)
        result = calc_ma(dates, closes, 5)
        for _, v in result:
            assert v is None


class TestCalcRSI:
    def test_all_up(self):
        """全上昇 → RSI = 100"""
        dates, closes = _make_data(30, step=1.0)
        result = calc_rsi(dates, closes, 14)
        # ウォームアップ後の最初のRSI
        assert result[14][1] == pytest.approx(100.0)

    def test_all_down(self):
        """全下落 → RSI = 0"""
        dates, closes = _make_data(30, start_price=200.0, step=-1.0)
        result = calc_rsi(dates, closes, 14)
        assert result[14][1] == pytest.approx(0.0)

    def test_mixed(self):
        """混合データ → RSI は 0〜100 の範囲"""
        dates = [date(2025, 1, i + 1) for i in range(30)]
        closes = [100 + (5 if i % 2 == 0 else -3) for i in range(30)]
        # cumulative sum
        cum = [100.0]
        for i in range(1, 30):
            cum.append(cum[-1] + (5 if i % 2 == 0 else -3))
        result = calc_rsi(dates, cum, 14)
        for d, v in result:
            if v is not None:
                assert 0.0 <= v <= 100.0

    def test_warmup_none(self):
        dates, closes = _make_data(30)
        result = calc_rsi(dates, closes, 14)
        # 最初の14個はNone
        for i in range(14):
            assert result[i][1] is None


class TestCalcMACD:
    def test_basic_structure(self):
        dates, closes = _make_data(50)
        result = calc_macd(dates, closes, 12, 26, 9)
        assert len(result) == 50
        # 最初の25個はMACD=None（slow EMA のウォームアップ）
        for i in range(25):
            assert result[i][1] is None

    def test_has_values(self):
        dates, closes = _make_data(50)
        result = calc_macd(dates, closes, 12, 26, 9)
        # 26日目以降にはMACDの値がある
        macd_values = [m for _, m, _, _ in result if m is not None]
        assert len(macd_values) > 0

    def test_histogram(self):
        """ヒストグラム = MACD - Signal"""
        dates, closes = _make_data(60)
        result = calc_macd(dates, closes, 12, 26, 9)
        for _, m, s, h in result:
            if m is not None and s is not None and h is not None:
                assert h == pytest.approx(m - s, abs=1e-10)


class TestCalcBollinger:
    def test_basic(self):
        dates, closes = _make_data(30)
        result = calc_bollinger(dates, closes, 5, 2.0)
        assert len(result) == 30
        # 最初の4つはNone
        for i in range(4):
            assert result[i][1] is None
        # index=4: window=[100,101,102,103,104], mean=102, std=sqrt(2)
        expected_std = math.sqrt(2)
        assert result[4][1] == pytest.approx(102.0 + 2 * expected_std)
        assert result[4][2] == pytest.approx(102.0)
        assert result[4][3] == pytest.approx(102.0 - 2 * expected_std)

    def test_upper_greater_than_lower(self):
        dates, closes = _make_data(30)
        result = calc_bollinger(dates, closes, 20, 2.0)
        for _, u, m, l in result:
            if u is not None:
                assert u > m > l

    def test_constant_prices(self):
        """全て同じ価格 → upper = middle = lower"""
        dates = [date(2025, 1, i + 1) for i in range(10)]
        closes = [100.0] * 10
        result = calc_bollinger(dates, closes, 5, 2.0)
        for _, u, m, l in result:
            if u is not None:
                assert u == pytest.approx(100.0)
                assert m == pytest.approx(100.0)
                assert l == pytest.approx(100.0)


class TestBoundaryMA:
    """MA の境界値テスト"""

    def test_data_exactly_period(self):
        """データ数 = period → 最後の1つだけ値あり"""
        dates, closes = _make_data(5)
        result = calc_ma(dates, closes, 5)
        for i in range(4):
            assert result[i][1] is None
        assert result[4][1] == pytest.approx(102.0)

    def test_data_one_less_than_period(self):
        """データ数 = period - 1 → 全てNone"""
        dates, closes = _make_data(4)
        result = calc_ma(dates, closes, 5)
        for _, v in result:
            assert v is None

    def test_data_one(self):
        """データ1件、period=1 → 値あり"""
        dates, closes = _make_data(1)
        result = calc_ma(dates, closes, 1)
        assert result[0][1] == pytest.approx(100.0)

    def test_empty_data(self):
        """データ0件"""
        result = calc_ma([], [], 5)
        assert result == []


class TestBoundaryRSI:
    """RSI の境界値テスト"""

    def test_data_exactly_period_plus_one(self):
        """データ数 = period + 1 → RSI値1つだけ"""
        dates, closes = _make_data(15, step=1.0)  # 15 = 14 + 1
        result = calc_rsi(dates, closes, 14)
        non_none = [(d, v) for d, v in result if v is not None]
        assert len(non_none) == 1

    def test_data_exactly_period(self):
        """データ数 = period → RSI値なし（全てNone）"""
        dates, closes = _make_data(14)
        result = calc_rsi(dates, closes, 14)
        for _, v in result:
            assert v is None

    def test_data_one(self):
        """データ1件 → 全てNone"""
        dates, closes = _make_data(1)
        result = calc_rsi(dates, closes, 14)
        assert len(result) == 1
        assert result[0][1] is None

    def test_empty_data(self):
        """データ0件"""
        result = calc_rsi([], [], 14)
        assert result == []


class TestBoundaryMACD:
    """MACD の境界値テスト"""

    def test_data_exactly_slow_period(self):
        """データ数 = slow(26) → MACD値1つだけ"""
        dates, closes = _make_data(26)
        result = calc_macd(dates, closes, 12, 26, 9)
        macd_values = [m for _, m, _, _ in result if m is not None]
        assert len(macd_values) == 1

    def test_data_one_less_than_slow(self):
        """データ数 = slow - 1 → MACD値なし"""
        dates, closes = _make_data(25)
        result = calc_macd(dates, closes, 12, 26, 9)
        macd_values = [m for _, m, _, _ in result if m is not None]
        assert len(macd_values) == 0

    def test_empty_data(self):
        """データ0件"""
        result = calc_macd([], [], 12, 26, 9)
        assert result == []


class TestBoundaryBollinger:
    """ボリンジャーバンドの境界値テスト"""

    def test_data_exactly_period(self):
        """データ数 = period → 最後の1つだけ値あり"""
        dates, closes = _make_data(20)
        result = calc_bollinger(dates, closes, 20, 2.0)
        non_none = [(d, u, m, l) for d, u, m, l in result if u is not None]
        assert len(non_none) == 1

    def test_data_one_less_than_period(self):
        """データ数 = period - 1 → 全てNone"""
        dates, closes = _make_data(19)
        result = calc_bollinger(dates, closes, 20, 2.0)
        for _, u, m, l in result:
            assert u is None

    def test_data_one(self):
        """データ1件"""
        dates, closes = _make_data(1)
        result = calc_bollinger(dates, closes, 1, 2.0)
        # period=1 → std=0 → upper=middle=lower=close
        assert result[0][1] == pytest.approx(100.0)
        assert result[0][2] == pytest.approx(100.0)
        assert result[0][3] == pytest.approx(100.0)

    def test_empty_data(self):
        """データ0件"""
        result = calc_bollinger([], [], 20, 2.0)
        assert result == []


# pytest.approx を import
import pytest
