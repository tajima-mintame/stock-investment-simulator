import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import FRONTEND_DIR
from database import init_db
from providers.jquants import JQuantsProvider
from routers import stocks, trades, portfolio, screening, collection, auto_trade
from tasks.collector import collect_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動・終了時の処理。"""
    logger.info("Initializing database...")
    init_db()

    # プロバイダーをルーターに注入（米国株は将来対応予定）
    providers = {
        "JP": JQuantsProvider(),
    }
    stocks.set_providers(providers)
    collection.set_providers(providers)
    auto_trade.set_providers(providers)
    logger.info("Providers initialized: JP (J-Quants)")

    # スケジューラー起動: 平日16:00 JST にデータ収集
    scheduler.add_job(
        collect_all,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=0, timezone="Asia/Tokyo"),
        args=[providers],
        id="daily_collection",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: daily collection at 16:00 JST (weekdays)")

    yield

    scheduler.shutdown(wait=False)
    logger.info("Shutting down...")


app = FastAPI(
    title="Stock Investment Simulator",
    description="株式投資シミュレーター API",
    version="0.1.0",
    lifespan=lifespan,
)

# ルーター登録
app.include_router(stocks.router)
app.include_router(trades.router)
app.include_router(portfolio.router)
app.include_router(screening.router)
app.include_router(collection.router)
app.include_router(auto_trade.router)


# ヘルスチェック
@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


# フロントエンド静的ファイル配信（最後にマウント）
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
