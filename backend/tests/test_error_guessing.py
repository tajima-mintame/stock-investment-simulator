"""エラー推測テスト: よくあるエラーパターン・異常入力を検証する。"""

import math
import pytest
from datetime import date, timedelta

from services.indicators import calc_ma, calc_rsi, calc_macd, calc_bollinger
from services.simulation import execute_trade, get_account_info, get_portfolio_holdings
from database import get_connection


def _add_stock(symbol, base_price=2800.0):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO stocks (symbol, market, name, sector, currency) "
            "VALUES (?, 'JP', ?, '輸送用機器', 'JPY')",
            (symbol, f"Test-{symbol}"),
        )
        for i in range(30):
            d = (date(2025, 1, 1) + timedelta(days=i)).isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO daily_prices (symbol, market, date, open, high, low, close, volume) "
                "VALUES (?, 'JP', ?, ?, ?, ?, ?, 500000)",
                (symbol, d, base_price, base_price + 10, base_price - 10, base_price + i),
            )
        conn.commit()
    finally:
        conn.close()


# === indicators エラー推測 ===

class TestIndicatorErrorGuessing:
    """指標計算の異常入力テスト"""

    def test_ma_dates_closes_length_mismatch(self):
        """dates と closes の長さが異なる"""
        dates = [date(2025, 1, i + 1) for i in range(10)]
        closes = [100.0 + i for i in range(5)]  # 長さ不一致
        # 短い方に合わせるか、IndexError が出るか
        # 現実装は zip されないので IndexError の可能性
        try:
            result = calc_ma(dates, closes, 3)
            # クラッシュしなければ、結果が closes 長に収まることを確認
            assert len(result) <= len(closes)
        except (IndexError, ValueError):
            pass  # エラーが出ても許容

    def test_rsi_all_same_price(self):
        """全て同じ価格 → 変動なし → RSIは定義上不定（0/0）"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]
        closes = [100.0] * 30
        result = calc_rsi(dates, closes, 14)
        # avg_gain=0, avg_loss=0 → RSI = 100 (0除算回避)
        for _, v in result:
            if v is not None:
                assert 0.0 <= v <= 100.0

    def test_bollinger_very_small_std(self):
        """ほぼ同じ価格 → std ≈ 0 → バンドが中央に収束"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]
        closes = [100.0 + i * 0.0001 for i in range(30)]
        result = calc_bollinger(dates, closes, 20, 2.0)
        for _, u, m, l in result:
            if u is not None:
                assert u >= m >= l
                assert (u - l) < 0.01  # バンド幅が極小

    def test_macd_insufficient_data_for_signal(self):
        """MACD値は出るがシグナル用データが不足"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(27)]
        closes = [100.0 + i for i in range(27)]
        result = calc_macd(dates, closes, 12, 26, 9)
        # MACD = 2値、signal にはまだデータ不足の可能性
        macd_vals = [m for _, m, _, _ in result if m is not None]
        assert len(macd_vals) >= 1

    def test_indicators_with_negative_prices(self):
        """負の価格（異常値）でもクラッシュしない"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(20)]
        closes = [-50.0 + i * 10 for i in range(20)]  # -50 → 140
        # クラッシュしないことが目的
        calc_ma(dates, closes, 5)
        calc_rsi(dates, closes, 14)
        calc_bollinger(dates, closes, 10, 2.0)

    def test_indicators_with_zero_prices(self):
        """価格0を含むデータ"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(20)]
        closes = [0.0] + [100.0 + i for i in range(19)]
        calc_ma(dates, closes, 5)
        calc_rsi(dates, closes, 14)
        calc_bollinger(dates, closes, 10, 2.0)

    def test_indicators_with_large_prices(self):
        """非常に大きな価格"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(30)]
        closes = [1e9 + i * 1000 for i in range(30)]
        ma = calc_ma(dates, closes, 5)
        non_none = [v for _, v in ma if v is not None]
        assert all(v > 1e9 for v in non_none)


# === simulation エラー推測 ===

class TestSimulationErrorGuessing:
    """売買の異常パターンテスト"""

    def test_buy_same_stock_many_times(self, test_db):
        """同一銘柄を何度も買う → 加重平均が正しく更新される"""
        _add_stock("7203")
        for i in range(10):
            execute_trade("7203", "JP", "BUY", 1, 2800.0 + i * 10)
        holdings = get_portfolio_holdings()
        assert holdings[0]["quantity"] == 10
        # avg = (2800+2810+2820+...+2890) / 10 = 2845
        assert holdings[0]["avg_cost"] == pytest.approx(2845.0)

    def test_sell_then_rebuy(self, test_db):
        """全売却後に再購入 → 新しい保有が作成される"""
        _add_stock("7203")
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        execute_trade("7203", "JP", "SELL", 10, 3000.0)
        assert len(get_portfolio_holdings()) == 0

        execute_trade("7203", "JP", "BUY", 5, 3100.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 1
        assert holdings[0]["quantity"] == 5
        assert holdings[0]["avg_cost"] == pytest.approx(3100.0)

    def test_floating_point_precision(self, test_db):
        """浮動小数点精度: 0.1 * 3 の丸め"""
        _add_stock("7203")
        execute_trade("7203", "JP", "BUY", 3, 0.1)
        info = get_account_info()
        # 100000 - 0.3 = 99999.7 (浮動小数点の精度内で)
        assert info["cash_balance"] == pytest.approx(100000.0 - 0.3, abs=1e-10)

    def test_very_small_trade(self, test_db):
        """最小取引: 1株 @ 0.01"""
        _add_stock("7203")
        execute_trade("7203", "JP", "BUY", 1, 0.01)
        holdings = get_portfolio_holdings()
        assert holdings[0]["quantity"] == 1
        assert holdings[0]["avg_cost"] == pytest.approx(0.01)

    def test_portfolio_without_price_data(self, test_db):
        """価格データなしの銘柄を保有"""
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO stocks (symbol, market, name, sector, currency) "
                "VALUES ('NODATA', 'JP', 'No Data Corp', '不明', 'JPY')"
            )
            conn.commit()
        finally:
            conn.close()

        execute_trade("NODATA", "JP", "BUY", 10, 100.0)
        holdings = get_portfolio_holdings()
        assert len(holdings) == 1
        assert holdings[0]["current_price"] is None
        assert holdings[0]["unrealized_pnl"] is None


# === API エラー推測 ===

class TestAPIErrorGuessing:
    """API レベルの異常入力テスト"""

    def test_trade_missing_symbol(self, app_client):
        """symbol 欠落 → 422"""
        resp = app_client.post(
            "/api/trades",
            json={"market": "JP", "side": "BUY", "quantity": 1, "price": 100.0},
        )
        assert resp.status_code == 422

    def test_trade_missing_quantity(self, app_client):
        """quantity 欠落 → 422"""
        resp = app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "price": 100.0},
        )
        assert resp.status_code == 422

    def test_trade_missing_price(self, app_client):
        """price 欠落 → 422"""
        resp = app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "quantity": 1},
        )
        assert resp.status_code == 422

    def test_trade_string_quantity(self, app_client):
        """quantity に文字列 → 422"""
        resp = app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "quantity": "ten", "price": 100.0},
        )
        assert resp.status_code == 422

    def test_trade_empty_body(self, app_client):
        """空ボディ → 422"""
        resp = app_client.post("/api/trades", json={})
        assert resp.status_code == 422

    def test_trade_with_note(self, app_client, seed_stock):
        """note付きの取引 → 成功"""
        resp = app_client.post(
            "/api/trades",
            json={
                "symbol": "7203",
                "market": "JP",
                "side": "BUY",
                "quantity": 1,
                "price": 2800.0,
                "note": "テスト購入",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["note"] == "テスト購入"

    def test_trade_with_unicode_note(self, app_client, seed_stock):
        """Unicode文字を含むnote"""
        resp = app_client.post(
            "/api/trades",
            json={
                "symbol": "7203",
                "market": "JP",
                "side": "BUY",
                "quantity": 1,
                "price": 2800.0,
                "note": "🚀 トヨタ買い増し！",
            },
        )
        assert resp.status_code == 200

    def test_indicators_invalid_period(self, app_client, seed_stock):
        """period=0 → BBは全てNoneで返る"""
        resp = app_client.get("/api/stocks/JP/7203/indicators?type=bb&period=0")
        assert resp.status_code == 200
        data = resp.json()
        # period=0 ではBBの値は全てNone
        for item in data["bollinger"]:
            assert item["upper"] is None

    def test_stocks_search_empty_q(self, app_client):
        """空の検索クエリ → 422（min_length=1）"""
        resp = app_client.get("/api/stocks/search?q=&market=JP")
        assert resp.status_code == 422

    def test_trade_filter_by_symbol(self, app_client, seed_stock):
        """取引履歴のsymbolフィルタ"""
        app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "quantity": 1, "price": 2800.0},
        )
        resp = app_client.get("/api/trades?symbol=7203")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = app_client.get("/api/trades?symbol=9999")
        assert resp.status_code == 200
        assert len(resp.json()) == 0
