from fastapi import APIRouter, Query

from services.auto_trader import setup_stocks, run_strategy, get_auto_trade_results, get_rankings, toggle_auto_trade

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
    return await setup_stocks(provider, count=count)


@router.post("/run")
async def run() -> dict:
    """全登録銘柄に対してスコアリング戦略を実行する。"""
    return run_strategy()


@router.post("/start")
async def start(count: int = Query(20)) -> dict:
    """ワンクリック運用開始: セットアップ→戦略実行を一括で行う。"""
    provider = _providers.get("JP")
    if provider is None:
        return {"error": "JP provider not available"}
    setup_result = await setup_stocks(provider, count=count)
    run_result = run_strategy()
    return {
        "setup": setup_result,
        "run": run_result,
    }


@router.get("/rankings")
async def rankings(
    sort_by: str = Query("score"),
    limit: int = Query(10),
) -> list[dict]:
    """銘柄スコアランキングを取得する。"""
    return get_rankings(sort_by=sort_by, limit=limit)


@router.post("/toggle")
async def toggle(enabled: bool = Query(...)) -> dict:
    """自動取引のON/OFFを切り替える。"""
    provider = _providers.get("JP")
    return toggle_auto_trade(enabled, provider)


@router.get("/results")
async def results() -> dict:
    """自動売買の結果（資産推移含む）を取得する。"""
    return get_auto_trade_results()
