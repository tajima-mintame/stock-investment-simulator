from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from database import get_connection
from models import (
    OHLCV,
    PriceListResponse,
    StockDetail,
    StockInfo,
    StockListResponse,
    SyncRequest,
    SyncResponse,
)
from providers.base import MarketDataProvider

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

# プロバイダーは main.py から注入される
_providers: dict[str, MarketDataProvider] = {}


def set_providers(providers: dict[str, MarketDataProvider]) -> None:
    _providers.update(providers)


def _get_provider(market: str) -> MarketDataProvider:
    provider = _providers.get(market)
    if provider is None:
        raise HTTPException(status_code=400, detail=f"Unknown market: {market}")
    return provider


@router.get("", response_model=StockListResponse)
async def list_stocks(
    market: str | None = Query(None),
    sector: str | None = Query(None),
    q: str | None = Query(None),
) -> StockListResponse:
    """登録済み銘柄の一覧を取得する。"""
    conn = get_connection()
    try:
        query_parts = ["SELECT symbol, market, name, sector, currency FROM stocks WHERE 1=1"]
        params: list = []
        if market:
            query_parts.append("AND market = ?")
            params.append(market)
        if sector:
            query_parts.append("AND sector = ?")
            params.append(sector)
        if q:
            query_parts.append("AND (symbol LIKE ? OR name LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])
        query_parts.append("ORDER BY symbol")

        rows = conn.execute(" ".join(query_parts), params).fetchall()
        stocks = [
            StockInfo(
                symbol=r["symbol"],
                market=r["market"],
                name=r["name"],
                sector=r["sector"],
                currency=r["currency"],
            )
            for r in rows
        ]
        return StockListResponse(stocks=stocks, total=len(stocks))
    finally:
        conn.close()


@router.get("/search")
async def search_stocks(
    q: str = Query(..., min_length=1),
    market: str = Query("US"),
) -> list[StockInfo]:
    """外部APIを使って銘柄を検索する。"""
    provider = _get_provider(market)
    results = await provider.search_stocks(q)
    return [
        StockInfo(
            symbol=s.symbol,
            market=s.market,
            name=s.name,
            sector=s.sector,
            currency=s.currency,
        )
        for s in results
    ]


@router.get("/{market}/{symbol}", response_model=StockDetail)
async def get_stock_detail(market: str, symbol: str) -> StockDetail:
    """銘柄詳細（プロフィール + 最新価格）を取得する。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT symbol, market, name, sector, currency FROM stocks WHERE symbol = ? AND market = ?",
            (symbol, market),
        ).fetchone()

        if row is None:
            # DBに未登録なら外部APIから取得
            provider = _get_provider(market)
            stock_data = await provider.get_stock_info(symbol)
            if stock_data is None:
                raise HTTPException(status_code=404, detail="Stock not found")
            info = StockInfo(
                symbol=stock_data.symbol,
                market=stock_data.market,
                name=stock_data.name,
                sector=stock_data.sector,
                currency=stock_data.currency,
            )
        else:
            info = StockInfo(
                symbol=row["symbol"],
                market=row["market"],
                name=row["name"],
                sector=row["sector"],
                currency=row["currency"],
            )

        # 最新価格を取得
        price_row = conn.execute(
            "SELECT date, open, high, low, close, volume FROM daily_prices "
            "WHERE symbol = ? AND market = ? ORDER BY date DESC LIMIT 1",
            (symbol, market),
        ).fetchone()

        latest_price = None
        if price_row:
            latest_price = OHLCV(
                date=date.fromisoformat(price_row["date"]),
                open=price_row["open"],
                high=price_row["high"],
                low=price_row["low"],
                close=price_row["close"],
                volume=price_row["volume"],
            )

        return StockDetail(info=info, latest_price=latest_price)
    finally:
        conn.close()


@router.get("/{market}/{symbol}/prices", response_model=PriceListResponse)
async def get_prices(
    market: str,
    symbol: str,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> PriceListResponse:
    """日足OHLCVを取得する。"""
    conn = get_connection()
    try:
        query_parts = [
            "SELECT date, open, high, low, close, volume FROM daily_prices "
            "WHERE symbol = ? AND market = ?"
        ]
        params: list = [symbol, market]

        if from_date:
            query_parts.append("AND date >= ?")
            params.append(from_date.isoformat())
        if to_date:
            query_parts.append("AND date <= ?")
            params.append(to_date.isoformat())
        query_parts.append("ORDER BY date ASC")

        rows = conn.execute(" ".join(query_parts), params).fetchall()
        prices = [
            OHLCV(
                date=date.fromisoformat(r["date"]),
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                volume=r["volume"],
            )
            for r in rows
        ]
        return PriceListResponse(symbol=symbol, market=market, prices=prices)
    finally:
        conn.close()


@router.post("/sync", response_model=SyncResponse)
async def sync_stock(req: SyncRequest) -> SyncResponse:
    """外部APIからデータを取得してDBに保存する。"""
    provider = _get_provider(req.market)

    # 銘柄情報を取得・登録
    stock_data = await provider.get_stock_info(req.symbol)
    if stock_data is None:
        raise HTTPException(status_code=404, detail="Stock not found in external API")

    conn = get_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO stocks (symbol, market, name, sector, currency, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                stock_data.symbol,
                stock_data.market,
                stock_data.name,
                stock_data.sector,
                stock_data.currency,
                now,
            ),
        )

        # 日足データ取得
        start = req.from_date or date(2024, 1, 1)
        end = req.to_date or date.today()
        prices = await provider.get_daily_prices(req.symbol, start, end)

        for p in prices:
            conn.execute(
                "INSERT OR REPLACE INTO daily_prices "
                "(symbol, market, date, open, high, low, close, volume, adj_close) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    req.symbol,
                    req.market,
                    p.date.isoformat(),
                    p.open,
                    p.high,
                    p.low,
                    p.close,
                    p.volume,
                    p.adj_close,
                ),
            )

        # 収集ログ記録
        conn.execute(
            "INSERT INTO collection_log (market, symbol, fetched_at, status, message) "
            "VALUES (?, ?, ?, ?, ?)",
            (req.market, req.symbol, now, "OK", f"Fetched {len(prices)} records"),
        )
        conn.commit()

        return SyncResponse(
            symbol=req.symbol,
            market=req.market,
            fetched_count=len(prices),
            message=f"Successfully synced {len(prices)} daily prices",
        )
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO collection_log (market, symbol, fetched_at, status, message) "
            "VALUES (?, ?, ?, ?, ?)",
            (req.market, req.symbol, now, "ERROR", str(e)),
        )
        conn.commit()
        raise HTTPException(status_code=500, detail="Failed to sync stock data") from e
    finally:
        conn.close()
