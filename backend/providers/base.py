from abc import ABC, abstractmethod
from datetime import date
from dataclasses import dataclass


@dataclass
class StockData:
    symbol: str
    market: str  # 'JP' or 'US'
    name: str
    sector: str | None
    currency: str


@dataclass
class PriceData:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float | None = None


class MarketDataProvider(ABC):
    """市場データプロバイダーの抽象基底クラス。"""

    @abstractmethod
    async def get_stock_info(self, symbol: str) -> StockData | None:
        """銘柄情報を取得する。"""
        ...

    @abstractmethod
    async def get_daily_prices(
        self, symbol: str, start: date, end: date
    ) -> list[PriceData]:
        """指定期間の日足OHLCVを取得する。"""
        ...

    @abstractmethod
    async def search_stocks(self, query: str) -> list[StockData]:
        """銘柄を検索する。"""
        ...
