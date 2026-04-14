from fastapi import APIRouter

from models import Holding, PortfolioResponse
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
