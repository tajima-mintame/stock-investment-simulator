from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import (
    AccountInfo,
    TradeRecord,
    TradeRequest,
    TradeStats,
)
from services.simulation import execute_trade, get_account_info, get_trade_stats

router = APIRouter(prefix="/api", tags=["trades"])


@router.get("/account", response_model=AccountInfo)
async def account() -> AccountInfo:
    """口座情報（残高 + ポートフォリオ時価総額）を取得する。"""
    return AccountInfo(**get_account_info())


@router.post("/trades", response_model=TradeRecord)
async def create_trade(req: TradeRequest) -> TradeRecord:
    """仮想取引を実行する。"""
    try:
        result = execute_trade(
            symbol=req.symbol,
            market=req.market,
            side=req.side,
            quantity=req.quantity,
            price=req.price,
            note=req.note,
        )
        return TradeRecord(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/trades", response_model=list[TradeRecord])
async def list_trades(
    symbol: str | None = Query(None),
    market: str | None = Query(None),
) -> list[TradeRecord]:
    """取引履歴を取得する。"""
    with get_db() as conn:
        query_parts = [
            "SELECT id, symbol, market, side, quantity, price, executed_at, note "
            "FROM trades WHERE 1=1"
        ]
        params: list = []
        if symbol:
            query_parts.append("AND symbol = ?")
            params.append(symbol)
        if market:
            query_parts.append("AND market = ?")
            params.append(market)
        query_parts.append("ORDER BY executed_at DESC")

        rows = conn.execute(" ".join(query_parts), params).fetchall()
        return [
            TradeRecord(
                id=r["id"],
                symbol=r["symbol"],
                market=r["market"],
                side=r["side"],
                quantity=r["quantity"],
                price=r["price"],
                executed_at=r["executed_at"],
                note=r["note"],
            )
            for r in rows
        ]


@router.get("/trades/stats", response_model=TradeStats)
async def trade_stats() -> TradeStats:
    """損益統計を取得する。"""
    return TradeStats(**get_trade_stats())
