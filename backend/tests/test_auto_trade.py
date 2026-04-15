"""自動売買のテスト。"""

import pytest
from datetime import date, timedelta

from helpers import add_stock
from database import get_db
from services.auto_trader import run_strategy, get_auto_trade_results, _evaluate_stock, _calc_quantity
from services.simulation import execute_trade


class TestEvaluateStock:
    def test_insufficient_data(self, test_db):
        add_stock("7203", days=10)
        result = _evaluate_stock("7203", "JP", 100000)
        assert result["action"] == "SKIP"
        assert "データ不足" in result["reason"]

    def test_hold_no_crossover(self, test_db):
        """クロスオーバーなし → HOLD"""
        # 単調増加データ → MA5 > MA25 で安定 → クロスなし
        add_stock("7203", base_price=1000, days=40)
        result = _evaluate_stock("7203", "JP", 100000)
        assert result["action"] in ("HOLD", "SKIP")

    def test_has_price(self, test_db):
        add_stock("7203", days=40)
        result = _evaluate_stock("7203", "JP", 100000)
        assert "price" in result


class TestCalcQuantity:
    def test_normal(self):
        # 100000 * 0.15 = 15000, price = 1000 → 15株
        assert _calc_quantity(100000, 1000) == 15

    def test_zero_price(self):
        assert _calc_quantity(100000, 0) == 0

    def test_expensive_stock(self):
        # 100000 * 0.15 = 15000, price = 50000 → 0株
        assert _calc_quantity(100000, 50000) == 0

    def test_small_balance(self):
        assert _calc_quantity(100, 1000) == 0


class TestRunStrategy:
    def test_no_watched_stocks(self, test_db):
        result = run_strategy()
        assert result["actions"] == 0
        assert result["details"] == []

    def test_with_watched_stock(self, test_db):
        add_stock("7203", days=40)
        with get_db() as conn:
            conn.execute("UPDATE stocks SET watched = 1 WHERE symbol = '7203'")
            conn.commit()
        result = run_strategy()
        assert "details" in result
        assert len(result["details"]) == 1


class TestGetAutoTradeResults:
    def test_no_trades(self, test_db):
        result = get_auto_trade_results()
        assert result["summary"]["total_stocks"] == 0
        assert result["results"] == []

    def test_with_trades(self, test_db):
        add_stock("7203", days=30)
        execute_trade("7203", "JP", "BUY", 10, 2800.0)
        execute_trade("7203", "JP", "SELL", 10, 3000.0)

        result = get_auto_trade_results()
        assert result["summary"]["total_stocks"] == 1
        assert result["summary"]["total_pnl"] == pytest.approx(2000.0)
        assert result["summary"]["win_count"] == 1
        assert result["results"][0]["symbol"] == "7203"
        assert result["results"][0]["status"] == "利益"

    def test_loss_trade(self, test_db):
        add_stock("7203", days=30)
        execute_trade("7203", "JP", "BUY", 10, 3000.0)
        execute_trade("7203", "JP", "SELL", 10, 2800.0)

        result = get_auto_trade_results()
        assert result["summary"]["total_pnl"] == pytest.approx(-2000.0)
        assert result["results"][0]["status"] == "損失"


class TestAutoTradeAPI:
    def test_results_empty(self, app_client):
        resp = app_client.get("/api/auto-trade/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_stocks"] == 0

    def test_run_no_stocks(self, app_client):
        resp = app_client.post("/api/auto-trade/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["actions"] == 0
