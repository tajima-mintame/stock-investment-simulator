from fastapi import APIRouter, Query

from database import get_db

router = APIRouter(prefix="/api/collection", tags=["collection"])

# プロバイダーは main.py から注入される
_providers: dict = {}


def set_providers(providers: dict) -> None:
    _providers.update(providers)


@router.get("/status")
async def collection_status(limit: int = Query(20)) -> list[dict]:
    """直近の収集ログを取得する。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, market, symbol, fetched_at, status, message "
            "FROM collection_log WHERE status != 'FUNDAMENTAL' "
            "ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


@router.post("/run")
async def run_collection() -> dict:
    """手動でデータ収集を実行する。"""
    from tasks.collector import collect_all

    result = await collect_all(_providers)
    return result


@router.post("/watch/{market}/{symbol}")
async def toggle_watch(market: str, symbol: str) -> dict:
    """銘柄のウォッチリスト状態をトグルする。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT watched FROM stocks WHERE symbol = ? AND market = ?",
            (symbol, market),
        ).fetchone()
        if row is None:
            return {"error": "Stock not found"}

        new_watched = 0 if row["watched"] else 1
        conn.execute(
            "UPDATE stocks SET watched = ? WHERE symbol = ? AND market = ?",
            (new_watched, symbol, market),
        )
        conn.commit()
        return {"symbol": symbol, "market": market, "watched": bool(new_watched)}
