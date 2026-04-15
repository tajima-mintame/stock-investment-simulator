import asyncio
import logging
from datetime import date

import jquantsapi

from config import JQUANTS_API_KEY
from providers.base import MarketDataProvider, PriceData, StockData

logger = logging.getLogger(__name__)


def _to_jquants_code(symbol: str) -> str:
    """銘柄コードをJ-Quants V2形式（末尾0付き5桁）に変換する。"""
    if len(symbol) == 4:
        return symbol + "0"
    return symbol


def _from_jquants_code(code: str) -> str:
    """J-Quants V2形式のコードを4桁銘柄コードに変換する。"""
    if len(code) == 5 and code.endswith("0"):
        return code[:4]
    return code


class JQuantsProvider(MarketDataProvider):
    """J-Quants API V2 を使った東証データプロバイダー。"""

    def __init__(self) -> None:
        self._client: jquantsapi.ClientV2 | None = None

    def _get_client(self) -> jquantsapi.ClientV2:
        if self._client is None:
            self._client = jquantsapi.ClientV2(api_key=JQUANTS_API_KEY)
        return self._client

    async def get_stock_info(self, symbol: str) -> StockData | None:
        """銘柄情報を取得する。"""
        try:
            jq_code = _to_jquants_code(symbol)
            df = await asyncio.to_thread(self._get_client().get_list)
            row = df[df["Code"] == jq_code]
            if row.empty:
                return None
            r = row.iloc[0]
            return StockData(
                symbol=symbol,
                market="JP",
                name=r.get("CoName", ""),
                sector=r.get("S33Nm", None),
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
            jq_code = _to_jquants_code(symbol)
            df = await asyncio.to_thread(
                self._get_client().get_eq_bars_daily,
                code=jq_code,
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
                        open=float(r.get("O", 0) or 0),
                        high=float(r.get("H", 0) or 0),
                        low=float(r.get("L", 0) or 0),
                        close=float(r.get("C", 0) or 0),
                        volume=int(r.get("Vo", 0) or 0),
                        adj_close=float(r["AdjC"]) if r.get("AdjC") else None,
                    )
                )
            return prices
        except Exception:
            logger.exception("J-Quants get_daily_prices failed for %s", symbol)
            return []

    async def search_stocks(self, query: str) -> list[StockData]:
        """銘柄名またはコードで検索する。"""
        try:
            df = await asyncio.to_thread(self._get_client().get_list)
            # 4桁コードでの検索にも対応
            jq_query = _to_jquants_code(query) if query.isdigit() and len(query) == 4 else query
            mask = df["Code"].str.contains(jq_query, na=False) | df[
                "CoName"
            ].str.contains(query, na=False)
            results: list[StockData] = []
            for _, r in df[mask].head(50).iterrows():
                results.append(
                    StockData(
                        symbol=_from_jquants_code(r["Code"]),
                        market="JP",
                        name=r.get("CoName", ""),
                        sector=r.get("S33Nm", None),
                        currency="JPY",
                    )
                )
            return results
        except Exception:
            logger.exception("J-Quants search_stocks failed for %s", query)
            return []
