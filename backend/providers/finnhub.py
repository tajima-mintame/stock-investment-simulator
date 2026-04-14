import asyncio
import logging
from datetime import date, datetime, timezone

import httpx

from config import FINNHUB_API_KEY
from providers.base import MarketDataProvider, PriceData, StockData

logger = logging.getLogger(__name__)

BASE_URL = "https://finnhub.io/api/v1"


class FinnhubProvider(MarketDataProvider):
    """Finnhub API を使った米国株データプロバイダー。"""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(30)  # 30 req/sec 上限

    def _headers(self) -> dict[str, str]:
        return {"X-Finnhub-Token": FINNHUB_API_KEY}

    async def _get(self, path: str, params: dict | None = None) -> dict | list | None:
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{BASE_URL}{path}",
                    params=params,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()

    async def get_stock_info(self, symbol: str) -> StockData | None:
        """銘柄プロフィールを取得する。"""
        try:
            data = await self._get(
                "/stock/profile2", params={"symbol": symbol}
            )
            if not data or not isinstance(data, dict) or not data.get("name"):
                return None
            return StockData(
                symbol=symbol,
                market="US",
                name=data.get("name", ""),
                sector=data.get("finnhubIndustry", None),
                currency="USD",
            )
        except Exception:
            logger.exception("Finnhub get_stock_info failed for %s", symbol)
            return None

    async def get_daily_prices(
        self, symbol: str, start: date, end: date
    ) -> list[PriceData]:
        """指定期間の日足データを取得する（/stock/candle）。"""
        try:
            start_ts = int(
                datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp()
            )
            end_ts = int(
                datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc).timestamp()
            )
            data = await self._get(
                "/stock/candle",
                params={
                    "symbol": symbol,
                    "resolution": "D",
                    "from": start_ts,
                    "to": end_ts,
                },
            )
            if not data or not isinstance(data, dict) or data.get("s") != "ok":
                return []

            prices: list[PriceData] = []
            timestamps = data.get("t", [])
            opens = data.get("o", [])
            highs = data.get("h", [])
            lows = data.get("l", [])
            closes = data.get("c", [])
            volumes = data.get("v", [])

            for i in range(len(timestamps)):
                dt = datetime.fromtimestamp(timestamps[i], tz=timezone.utc).date()
                prices.append(
                    PriceData(
                        date=dt,
                        open=float(opens[i]),
                        high=float(highs[i]),
                        low=float(lows[i]),
                        close=float(closes[i]),
                        volume=int(volumes[i]),
                    )
                )
            return prices
        except Exception:
            logger.exception("Finnhub get_daily_prices failed for %s", symbol)
            return []

    async def search_stocks(self, query: str) -> list[StockData]:
        """銘柄を検索する（/search）。"""
        try:
            data = await self._get("/search", params={"q": query})
            if not data or not isinstance(data, dict):
                return []

            results: list[StockData] = []
            for item in data.get("result", [])[:50]:
                # 米国株のみに限定（type=Common Stock）
                if item.get("type") not in ("Common Stock", "EQS"):
                    continue
                results.append(
                    StockData(
                        symbol=item.get("symbol", ""),
                        market="US",
                        name=item.get("description", ""),
                        sector=None,
                        currency="USD",
                    )
                )
            return results
        except Exception:
            logger.exception("Finnhub search_stocks failed for %s", query)
            return []
