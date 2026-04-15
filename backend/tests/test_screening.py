"""スクリーニングのUT。"""

import pytest

from helpers import add_stock
from services.screening import screen_stocks


class TestScreenStocks:
    def test_no_stocks(self, test_db):
        results = screen_stocks()
        assert results == []

    def test_returns_stocks_with_data(self, test_db):
        add_stock("7203", name="トヨタ", sector="輸送用機器")
        results = screen_stocks()
        assert len(results) == 1
        assert results[0]["symbol"] == "7203"
        assert results[0]["avg_volume"] > 0
        assert results[0]["volatility"] >= 0

    def test_sector_filter(self, test_db):
        add_stock("7203", name="トヨタ", sector="輸送用機器")
        add_stock("9984", name="ソフトバンクG", sector="情報・通信業")

        results = screen_stocks(sector="輸送用機器")
        assert len(results) == 1
        assert results[0]["symbol"] == "7203"

    def test_min_volume_filter(self, test_db):
        add_stock("7203")
        results = screen_stocks(min_volume=999999)
        # テストデータの出来高は500000なのでフィルタされる
        assert len(results) == 0

    def test_max_volume_filter(self, test_db):
        add_stock("7203")
        results = screen_stocks(max_volume=1)
        assert len(results) == 0

    def test_sort_by_volatility(self, test_db):
        add_stock("7203", base_price=2800)
        add_stock("9984", base_price=100)  # 価格が低い方がボラティリティ%が高い
        results = screen_stocks(sort_by="volatility")
        assert len(results) == 2
        assert results[0]["volatility"] >= results[1]["volatility"]

    def test_sort_by_change_pct(self, test_db):
        add_stock("7203", base_price=2800)
        add_stock("9984", base_price=6000)
        results = screen_stocks(sort_by="change_pct")
        assert len(results) == 2

    def test_insufficient_data_excluded(self, test_db):
        """1日分しかデータがない銘柄は除外される"""
        add_stock("7203", days=1)
        results = screen_stocks()
        assert len(results) == 0

    def test_market_filter(self, test_db):
        add_stock("7203")
        results = screen_stocks(market="US")
        assert len(results) == 0
        results = screen_stocks(market="JP")
        assert len(results) == 1
