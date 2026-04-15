import os
import sys

import pytest

# backend/ をモジュール検索パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# tests/ もモジュール検索パスに追加（helpers.py 参照用）
sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """テスト用の一時DBを作成し、テストごとにクリーンな状態にする。"""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    monkeypatch.setattr("config.INITIAL_BALANCE", 100000.0)
    monkeypatch.setattr("database.INITIAL_BALANCE", 100000.0)

    from database import init_db

    init_db()
    yield db_path


@pytest.fixture
def seed_stock(test_db):
    """トヨタ(7203)のテストデータを投入する。close = 2800+i*10+5 (30日分)。"""
    from database import get_db

    with get_db() as conn:
        conn.execute(
            "INSERT INTO stocks (symbol, market, name, sector, currency) "
            "VALUES ('7203', 'JP', 'トヨタ自動車', '輸送用機器', 'JPY')"
        )
        for i in range(30):
            day = f"2025-01-{i + 1:02d}"
            base = 2800.0 + i * 10
            conn.execute(
                "INSERT INTO daily_prices (symbol, market, date, open, high, low, close, volume) "
                "VALUES ('7203', 'JP', ?, ?, ?, ?, ?, ?)",
                (day, base, base + 20, base - 10, base + 5, 1000000 + i * 10000),
            )
        conn.commit()


@pytest.fixture
def app_client(test_db, monkeypatch):
    """FastAPI TestClient を返す。テスト時はスケジューラーを無効化。"""
    from fastapi.testclient import TestClient
    from main import app, scheduler
    from providers.jquants import JQuantsProvider
    from routers import stocks, collection, auto_trade

    # スケジューラーをテスト時に無効化
    monkeypatch.setattr(scheduler, "start", lambda: None)
    monkeypatch.setattr(scheduler, "shutdown", lambda **kw: None)

    providers = {"JP": JQuantsProvider()}
    stocks.set_providers(providers)
    collection.set_providers(providers)
    auto_trade.set_providers(providers)

    with TestClient(app) as client:
        yield client
