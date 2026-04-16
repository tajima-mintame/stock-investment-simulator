import logging

from fastapi import APIRouter, Query

from services.auto_trader import setup_stocks, run_strategy, get_auto_trade_results, get_rankings, toggle_auto_trade

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auto-trade", tags=["auto-trade"])

_providers: dict = {}


def set_providers(providers: dict) -> None:
    _providers.update(providers)


@router.post("/setup")
async def setup(count: int = Query(20)) -> dict:
    """出来高上位の銘柄を自動登録・同期する。"""
    provider = _providers.get("JP")
    if provider is None:
        return {"error": "JP provider not available"}
    try:
        return await setup_stocks(provider, count=count)
    except Exception as e:
        logger.exception("setup failed")
        return {"registered": 0, "errors": 1, "message": str(e)}


@router.post("/run")
async def run() -> dict:
    """全登録銘柄に対してスコアリング戦略を実行する。"""
    try:
        return run_strategy()
    except Exception as e:
        logger.exception("run failed")
        return {"actions": 0, "buys": 0, "sells": 0, "skipped": 0, "details": [], "error": str(e)}


@router.post("/start")
async def start(count: int = Query(20)) -> dict:
    """ワンクリック運用開始: セットアップ→戦略実行を一括で行う。"""
    provider = _providers.get("JP")
    if provider is None:
        return {"error": "JP provider not available"}
    try:
        setup_result = await setup_stocks(provider, count=count)
    except Exception as e:
        logger.exception("start/setup failed")
        return {"setup": {"registered": 0, "errors": 1, "message": str(e)}, "run": None}
    try:
        run_result = run_strategy()
    except Exception as e:
        logger.exception("start/run failed")
        return {"setup": setup_result, "run": {"actions": 0, "error": str(e)}}
    return {"setup": setup_result, "run": run_result}


@router.get("/rankings")
async def rankings(
    sort_by: str = Query("score"),
    limit: int = Query(10),
) -> list[dict]:
    """銘柄スコアランキングを取得する。"""
    try:
        return get_rankings(sort_by=sort_by, limit=limit)
    except Exception as e:
        logger.exception("rankings failed")
        return []


@router.post("/toggle")
async def toggle(enabled: bool = Query(...)) -> dict:
    """自動取引のON/OFFを切り替える。"""
    try:
        provider = _providers.get("JP")
        return toggle_auto_trade(enabled, provider)
    except Exception as e:
        logger.exception("toggle failed")
        return {"error": str(e)}


@router.get("/results")
async def results() -> dict:
    """自動売買の結果（資産推移含む）を取得する。"""
    try:
        return get_auto_trade_results()
    except Exception as e:
        logger.exception("results failed")
        return {"summary": {"total_stocks": 0, "total_pnl": 0, "win_count": 0, "lose_count": 0, "win_rate": 0, "current_total": 0, "initial_balance": 100000, "return_pct": 0}, "results": [], "snapshots": [], "error": str(e)}
