import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import FRONTEND_DIR
from database import init_db
from providers.jquants import JQuantsProvider
from routers import stocks, trades, portfolio, screening

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


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
    logger.info("Providers initialized: JP (J-Quants)")

    yield

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


# ヘルスチェック
@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


# フロントエンド静的ファイル配信（最後にマウント）
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
