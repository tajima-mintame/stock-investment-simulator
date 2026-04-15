import pytest


class TestHealth:
    def test_health(self, app_client):
        resp = app_client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestAccount:
    def test_initial_balance(self, app_client):
        resp = app_client.get("/api/account")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cash_balance"] == pytest.approx(100000.0)
        assert data["portfolio_value"] == pytest.approx(0.0)
        assert data["total_value"] == pytest.approx(100000.0)


class TestStocks:
    def test_list_empty(self, app_client):
        resp = app_client.get("/api/stocks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stocks"] == []
        assert data["total"] == 0

    def test_stock_not_found(self, app_client):
        resp = app_client.get("/api/stocks/JP/9999")
        # 外部APIも呼べないのでエラーになる
        assert resp.status_code in (404, 500)


class TestTrades:
    def test_list_empty(self, app_client):
        resp = app_client.get("/api/trades")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_stats_empty(self, app_client):
        resp = app_client.get("/api/trades/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 0

    def test_trade_unknown_stock(self, app_client):
        resp = app_client.post(
            "/api/trades",
            json={
                "symbol": "9999",
                "market": "JP",
                "side": "BUY",
                "quantity": 1,
                "price": 100.0,
            },
        )
        assert resp.status_code == 400

    def test_trade_buy_and_list(self, app_client, seed_stock):
        # Buy
        resp = app_client.post(
            "/api/trades",
            json={
                "symbol": "7203",
                "market": "JP",
                "side": "BUY",
                "quantity": 10,
                "price": 2850.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["side"] == "BUY"
        assert data["quantity"] == 10

        # List
        resp = app_client.get("/api/trades")
        assert resp.status_code == 200
        trades = resp.json()
        assert len(trades) == 1
        assert trades[0]["symbol"] == "7203"

        # Account updated
        resp = app_client.get("/api/account")
        data = resp.json()
        assert data["cash_balance"] == pytest.approx(100000 - 28500)


class TestPortfolio:
    def test_empty(self, app_client):
        resp = app_client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["holdings"] == []

    def test_with_holdings(self, app_client, seed_stock):
        app_client.post(
            "/api/trades",
            json={
                "symbol": "7203",
                "market": "JP",
                "side": "BUY",
                "quantity": 10,
                "price": 2850.0,
            },
        )
        resp = app_client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["quantity"] == 10


class TestTradesSell:
    """SELL操作のAPI検証"""

    def test_sell_success(self, app_client, seed_stock):
        app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "quantity": 10, "price": 2850.0},
        )
        resp = app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "SELL", "quantity": 5, "price": 3000.0},
        )
        assert resp.status_code == 200
        assert resp.json()["side"] == "SELL"
        assert resp.json()["quantity"] == 5

    def test_sell_insufficient(self, app_client, seed_stock):
        resp = app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "SELL", "quantity": 1, "price": 3000.0},
        )
        assert resp.status_code == 400

    def test_sell_all_clears_portfolio(self, app_client, seed_stock):
        app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "quantity": 10, "price": 2850.0},
        )
        app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "SELL", "quantity": 10, "price": 3000.0},
        )
        resp = app_client.get("/api/portfolio")
        assert resp.json()["holdings"] == []

    def test_stats_after_win_trade(self, app_client, seed_stock):
        app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "quantity": 10, "price": 2800.0},
        )
        app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "SELL", "quantity": 10, "price": 3000.0},
        )
        resp = app_client.get("/api/trades/stats")
        data = resp.json()
        assert data["total_realized_pnl"] == pytest.approx(2000.0)
        assert data["win_rate"] == pytest.approx(1.0)


class TestPortfolioStates:
    """ポートフォリオの利益/損失/ゼロ状態"""

    def test_portfolio_unrealized_profit(self, app_client, seed_stock):
        """含み益: 買値 < 現在価格"""
        app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "quantity": 10, "price": 2800.0},
        )
        resp = app_client.get("/api/portfolio")
        data = resp.json()
        # 最新close = 2800 + 29*10 + 5 = 3095, avg_cost = 2800
        assert data["holdings"][0]["unrealized_pnl"] > 0
        assert data["total_unrealized_pnl"] > 0

    def test_portfolio_unrealized_loss(self, app_client, seed_stock):
        """含み損: 買値 > 現在価格"""
        app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "quantity": 10, "price": 9000.0},
        )
        resp = app_client.get("/api/portfolio")
        data = resp.json()
        assert data["holdings"][0]["unrealized_pnl"] < 0
        assert data["total_unrealized_pnl"] < 0


class TestIndicators:
    def test_indicators_with_data(self, app_client, seed_stock):
        resp = app_client.get(
            "/api/stocks/JP/7203/indicators?type=ma,rsi,macd,bb"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "7203"
        assert data["market"] == "JP"
        assert "5" in data["ma"]
        assert "25" in data["ma"]
        assert "75" in data["ma"]
        assert len(data["rsi"]) == 30
        assert len(data["macd"]) == 30
        assert len(data["bollinger"]) == 30

    def test_indicators_no_data(self, app_client):
        resp = app_client.get(
            "/api/stocks/JP/9999/indicators?type=ma"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ma"] is None


class TestScreening:
    def test_screening_empty(self, app_client):
        resp = app_client.get("/api/screening")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_screening_with_data(self, app_client, seed_stock):
        resp = app_client.get("/api/screening?market=JP")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["symbol"] == "7203"
        assert "avg_volume" in results[0]
        assert "volatility" in results[0]

    def test_screening_sort(self, app_client, seed_stock):
        resp = app_client.get("/api/screening?sort_by=volatility")
        assert resp.status_code == 200


class TestAllocation:
    def test_allocation_empty(self, app_client):
        resp = app_client.get("/api/portfolio/allocation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["by_market"] == []
        assert data["by_sector"] == []

    def test_allocation_with_holdings(self, app_client, seed_stock):
        app_client.post(
            "/api/trades",
            json={"symbol": "7203", "market": "JP", "side": "BUY", "quantity": 10, "price": 2800.0},
        )
        resp = app_client.get("/api/portfolio/allocation")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["by_market"]) == 1
        assert len(data["by_sector"]) == 1
        assert data["by_sector"][0]["percentage"] == pytest.approx(1.0)


class TestCorrelation:
    def test_correlation_empty(self, app_client):
        resp = app_client.get("/api/portfolio/correlation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["matrix"] == []
