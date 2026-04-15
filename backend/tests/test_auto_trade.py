"""自動売買のテスト。"""

import pytest
from datetime import date, timedelta

from helpers import add_stock
from database import get_db
from services.auto_trader import (
    run_strategy, get_auto_trade_results, _score_stock,
    _calc_quantity, _calc_technical_score, _calc_fundamental_score,
    _save_snapshot,
)
from services.simulation import execute_trade


class TestScoreStock:
    def test_insufficient_data(self, test_db):
        add_stock("7203", days=10)
        result = _score_stock("7203", "JP")
        assert result["action"] == "SKIP"

    def test_has_score(self, test_db):
        add_stock("7203", days=40)
        result = _score_stock("7203", "JP")
        assert "score" in result
        assert "tech_score" in result
        assert "fund_score" in result

    def test_score_range(self, test_db):
        add_stock("7203", days=40)
        result = _score_stock("7203", "JP")
        assert -100 <= result["tech_score"] <= 100


class TestTechnicalScore:
    def test_basic(self, test_db):
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(40)]
        closes = [1000.0 + i * 5 for i in range(40)]
        score = _calc_technical_score(dates, closes)
        assert -100 <= score <= 100

    def test_uptrend_ma_above(self, test_db):
        """単調増加 → MA5>MA25（上昇トレンド）でプラスだがクロスなしで控えめ"""
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(50)]
        closes = [1000.0 + i * 10 for i in range(50)]
        score = _calc_technical_score(dates, closes)
        # MA5>MA25 (+10) だが RSI>60 (-10) で相殺される可能性あり
        assert -30 <= score <= 30


class TestFundamentalScore:
    def test_no_data(self, test_db):
        score = _calc_fundamental_score("NODATA", 1000.0)
        assert score == 0.0  # データなしは中立

    def test_with_data(self, test_db):
        # ファンダメンタルデータを手動で挿入
        with get_db() as conn:
            conn.execute(
                "INSERT INTO collection_log (market, symbol, fetched_at, status, message) "
                "VALUES ('JP', '7203', '2025-01-01', 'FUNDAMENTAL', "
                "'EPS=200,FEPS=250,Sales=30000000000000,FSales=35000000000000,DivAnn=90,BPS=2000,EqAR=0.4')"
            )
            conn.commit()
        score = _calc_fundamental_score("7203", 3000.0)
        assert -100 <= score <= 100
        # PER = 3000/250 = 12 → 割安(+15)
        # 配当利回り = 90/3000*100 = 3% → (+15)
        # 売上成長 = (35-30)/30 = 16.7% → (+25)
        # 自己資本 = 0.4 → (+10)
        assert score > 0


class TestCalcQuantity:
    def test_high_score(self):
        # score=80, cash=100000, price=1000
        # factor = 80/100 = 0.8, amount = 100000*0.20*0.8 = 16000, qty = 16
        assert _calc_quantity(100000, 1000, 80) == 16

    def test_low_score(self):
        # score=30, factor = 0.3, amount = 100000*0.20*0.3 = 6000, qty = 6
        assert _calc_quantity(100000, 1000, 30) == 6

    def test_zero_price(self):
        assert _calc_quantity(100000, 0, 50) == 0


class TestRunStrategy:
    def test_no_watched(self, test_db):
        result = run_strategy()
        assert result["actions"] == 0

    def test_with_watched(self, test_db):
        add_stock("7203", days=40)
        with get_db() as conn:
            conn.execute("UPDATE stocks SET watched = 1 WHERE symbol = '7203'")
            conn.commit()
        result = run_strategy()
        assert "details" in result
        assert len(result["details"]) == 1

    def test_saves_snapshot(self, test_db):
        add_stock("7203", days=40)
        with get_db() as conn:
            conn.execute("UPDATE stocks SET watched = 1 WHERE symbol = '7203'")
            conn.commit()
        run_strategy()
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM asset_snapshots").fetchone()[0]
        assert count >= 1


class TestSaveSnapshot:
    def test_snapshot(self, test_db):
        _save_snapshot()
        with get_db() as conn:
            row = conn.execute("SELECT * FROM asset_snapshots ORDER BY id DESC LIMIT 1").fetchone()
        assert row["total"] == pytest.approx(100000.0)
        assert row["cash"] == pytest.approx(100000.0)
        assert row["portfolio"] == pytest.approx(0.0)


class TestGetResults:
    def test_empty(self, test_db):
        result = get_auto_trade_results()
        assert result["summary"]["total_stocks"] == 0
        assert result["snapshots"] == []

    def test_with_trades(self, test_db):
        add_stock("7203", days=30)
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        execute_trade("7203", "JP", "SELL", 10, 3000.0)
        _save_snapshot()

        result = get_auto_trade_results()
        assert result["summary"]["total_pnl"] == pytest.approx(2000.0)
        assert result["summary"]["current_total"] > 0
        assert result["summary"]["return_pct"] is not None
        assert len(result["snapshots"]) >= 1

    def test_return_pct(self, test_db):
        result = get_auto_trade_results()
        assert result["summary"]["initial_balance"] == 100000.0


class TestAutoTradeAPI:
    def test_results(self, app_client):
        resp = app_client.get("/api/auto-trade/results")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "snapshots" in data

    def test_run(self, app_client):
        resp = app_client.post("/api/auto-trade/run")
        assert resp.status_code == 200
