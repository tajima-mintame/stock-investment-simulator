import os
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルート（backend/の親ディレクトリ）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

# API Keys
JQUANTS_API_KEY: str = os.getenv("JQUANTS_API_KEY", "")
FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")

# Database
DB_PATH: str = os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "simulator.db"))

# Server
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))

# Virtual account
INITIAL_BALANCE: float = float(os.getenv("INITIAL_BALANCE", "10000000"))

# Frontend static files
FRONTEND_DIR: str = str(PROJECT_ROOT / "frontend")
