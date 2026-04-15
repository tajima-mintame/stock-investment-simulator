from fastapi import APIRouter, Query

from models import ScreeningResult
from services.screening import screen_stocks

router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.get("", response_model=list[ScreeningResult])
async def screening(
    market: str | None = Query(None),
    sector: str | None = Query(None),
    min_volume: int | None = Query(None),
    max_volume: int | None = Query(None),
    min_volatility: float | None = Query(None),
    max_volatility: float | None = Query(None),
    sort_by: str = Query("volume"),
) -> list[ScreeningResult]:
    """銘柄をスクリーニングする。"""
    results = screen_stocks(
        market=market,
        sector=sector,
        min_volume=min_volume,
        max_volume=max_volume,
        min_volatility=min_volatility,
        max_volatility=max_volatility,
        sort_by=sort_by,
    )
    return [ScreeningResult(**r) for r in results]
