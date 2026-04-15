from fastapi import APIRouter

from models import AllocationResponse, AllocationItem, Holding, PortfolioResponse
from services.portfolio import get_allocation, get_correlation
from services.simulation import get_portfolio_holdings

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioResponse)
async def portfolio() -> PortfolioResponse:
    """保有銘柄一覧（含み損益付き）を取得する。"""
    holdings_data = get_portfolio_holdings()
    holdings = [Holding(**h) for h in holdings_data]
    total_unrealized = sum(
        h.unrealized_pnl for h in holdings if h.unrealized_pnl is not None
    )
    return PortfolioResponse(holdings=holdings, total_unrealized_pnl=total_unrealized)


@router.get("/allocation", response_model=AllocationResponse)
async def allocation() -> AllocationResponse:
    """セクター別・市場別の資産配分を取得する。"""
    data = get_allocation()
    return AllocationResponse(
        by_market=[AllocationItem(**i) for i in data["by_market"]],
        by_sector=[AllocationItem(**i) for i in data["by_sector"]],
    )


@router.get("/correlation")
async def correlation() -> dict:
    """保有銘柄間の相関行列を取得する。"""
    return get_correlation()
