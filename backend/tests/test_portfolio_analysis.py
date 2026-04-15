"""ポートフォリオ分析のUT。"""

import pytest

from helpers import add_stock
from services.portfolio import get_allocation, get_correlation
from services.simulation import execute_trade


class TestGetAllocation:
    def test_empty_portfolio(self, test_db):
        result = get_allocation()
        assert result["by_market"] == []
        assert result["by_sector"] == []

    def test_single_holding(self, test_db):
        add_stock("7203", name="トヨタ", sector="輸送用機器")
        execute_trade("7203", "JP", "BUY", 10, 2800.0)

        result = get_allocation()
        assert len(result["by_market"]) == 1
        assert result["by_market"][0]["label"] == "JP"
        assert result["by_market"][0]["percentage"] == pytest.approx(1.0)

        assert len(result["by_sector"]) == 1
        assert result["by_sector"][0]["label"] == "輸送用機器"
        assert result["by_sector"][0]["percentage"] == pytest.approx(1.0)

    def test_multiple_sectors(self, test_db):
        add_stock("7203", name="トヨタ", sector="輸送用機器", base_price=2800)
        add_stock("9984", name="ソフトバンクG", sector="情報・通信業", base_price=6000)

        execute_trade("7203", "JP", "BUY", 5, 2800.0)
        execute_trade("9984", "JP", "BUY", 2, 6000.0)

        result = get_allocation()
        assert len(result["by_sector"]) == 2
        total_pct = sum(s["percentage"] for s in result["by_sector"])
        assert total_pct == pytest.approx(1.0)

    def test_all_same_sector(self, test_db):
        add_stock("7203", name="トヨタ", sector="輸送用機器", base_price=2800)
        add_stock("7267", name="ホンダ", sector="輸送用機器", base_price=1500)

        execute_trade("7203", "JP", "BUY", 5, 2800.0)
        execute_trade("7267", "JP", "BUY", 5, 1500.0)

        result = get_allocation()
        assert len(result["by_sector"]) == 1
        assert result["by_sector"][0]["label"] == "輸送用機器"
        assert result["by_sector"][0]["percentage"] == pytest.approx(1.0)


class TestGetCorrelation:
    def test_no_holdings(self, test_db):
        result = get_correlation()
        assert result["symbols"] == []
        assert result["matrix"] == []

    def test_single_holding(self, test_db):
        add_stock("7203")
        execute_trade("7203", "JP", "BUY", 5, 2800.0)

        result = get_correlation()
        assert len(result["symbols"]) == 1
        assert result["matrix"] == []  # 2銘柄以上必要

    def test_two_holdings(self, test_db):
        add_stock("7203", base_price=2800, days=30)
        add_stock("9984", base_price=6000, days=30)

        execute_trade("7203", "JP", "BUY", 5, 2800.0)
        execute_trade("9984", "JP", "BUY", 2, 6000.0)

        result = get_correlation()
        assert len(result["symbols"]) == 2
        assert len(result["matrix"]) == 2
        assert len(result["matrix"][0]) == 2
        # 対角は1.0
        assert result["matrix"][0][0] == pytest.approx(1.0)
        assert result["matrix"][1][1] == pytest.approx(1.0)
        # 相関値は-1〜1の範囲
        corr = result["matrix"][0][1]
        if corr is not None:
            assert -1.0 <= corr <= 1.0

    def test_three_holdings(self, test_db):
        add_stock("7203", base_price=2800, days=30)
        add_stock("9984", base_price=6000, days=30)
        add_stock("6758", base_price=3200, days=30)

        execute_trade("7203", "JP", "BUY", 3, 2800.0)
        execute_trade("9984", "JP", "BUY", 1, 6000.0)
        execute_trade("6758", "JP", "BUY", 2, 3200.0)

        result = get_correlation()
        assert len(result["symbols"]) == 3
        assert len(result["matrix"]) == 3
        # 対称行列: matrix[i][j] == matrix[j][i]
        for i in range(3):
            for j in range(3):
                if result["matrix"][i][j] is not None and result["matrix"][j][i] is not None:
                    assert result["matrix"][i][j] == pytest.approx(
                        result["matrix"][j][i], abs=1e-10
                    )
