import asyncio
import logging
from datetime import date

import jquantsapi

from config import JQUANTS_API_KEY
from providers.base import MarketDataProvider, PriceData, StockData

logger = logging.getLogger(__name__)


class JQuantsProvider(MarketDataProvider):
    """J-Quants API V2 を使った東証データプロバイダー。"""

    def __init__(self) -> None:
        self._client: jquantsapi.Client | None = None

    def _get_client(self) -> jquantsapi.Client:
        if self._client is None:
            self._client = jquantsapi.Client(api_key=JQUANTS_API_KEY)
        return self._client

    async def get_stock_info(self, symbol: str) -> StockData | None:
        """銘柄情報を取得する。J-Quantsの上場銘柄一覧から検索。"""
        try:
            df = await asyncio.to_thread(self._get_client().get_listed_info)
            row = df[df["Code"] == symbol]
            if row.empty:
                return None
            r = row.iloc[0]
            return StockData(
                symbol=symbol,
                market="JP",
                name=r.get("CompanyName", ""),
                sector=r.get("Sector33CodeName", None),
                currency="JPY",
            )
        except Exception:
            logger.exception("J-Quants get_stock_info failed for %s", symbol)
            return None

    async def get_daily_prices(
        self, symbol: str, start: date, end: date
    ) -> list[PriceData]:
        """指定期間の日足データを取得する。"""
        try:
            df = await asyncio.to_thread(
                self._get_client().get_prices_daily_quotes,
                code=symbol,
                from_yyyymmdd=start.strftime("%Y%m%d"),
                to_yyyymmdd=end.strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                return []

            prices: list[PriceData] = []
            for _, r in df.iterrows():
                prices.append(
                    PriceData(
                        date=date.fromisoformat(str(r["Date"])[:10]),
                        open=float(r.get("Open", 0) or 0),
                        high=float(r.get("High", 0) or 0),
                        low=float(r.get("Low", 0) or 0),
                        close=float(r.get("Close", 0) or 0),
                        volume=int(r.get("Volume", 0) or 0),
                        adj_close=float(r["AdjustmentClose"])
                        if r.get("AdjustmentClose")
                        else None,
                    )
                )
            return prices
        except Exception:
            logger.exception("J-Quants get_daily_prices failed for %s", symbol)
            return []

    async def search_stocks(self, query: str) -> list[StockData]:
        """銘柄名またはコードで検索する。"""
        try:
            df = await asyncio.to_thread(self._get_client().get_listed_info)
            mask = df["Code"].str.contains(query, na=False) | df[
                "CompanyName"
            ].str.contains(query, na=False)
            results: list[StockData] = []
            for _, r in df[mask].head(50).iterrows():
                results.append(
                    StockData(
                        symbol=r["Code"],
                        market="JP",
                        name=r.get("CompanyName", ""),
                        sector=r.get("Sector33CodeName", None),
                        currency="JPY",
                    )
                )
            return results
        except Exception:
            logger.exception("J-Quants search_stocks failed for %s", query)
            return []
