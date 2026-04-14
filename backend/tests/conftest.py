import os
import sys
import tempfile

import pytest

# backend/ をモジュール検索パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


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
    """テスト用の銘柄と価格データを投入する。"""
    from database import get_connection

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO stocks (symbol, market, name, sector, currency) "
            "VALUES ('7203', 'JP', 'トヨタ自動車', '輸送用機器', 'JPY')"
        )

        # 30日分のテストデータ（2025-01-01〜2025-01-30）
        for i in range(30):
            day = f"2025-01-{i + 1:02d}"
            base = 2800.0 + i * 10  # 2800 → 3090
            conn.execute(
                "INSERT INTO daily_prices (symbol, market, date, open, high, low, close, volume) "
                "VALUES ('7203', 'JP', ?, ?, ?, ?, ?, ?)",
                (day, base, base + 20, base - 10, base + 5, 1000000 + i * 10000),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def app_client(test_db):
    """FastAPI TestClient を返す。"""
    from fastapi.testclient import TestClient
    from main import app
    from database import init_db
    from providers.jquants import JQuantsProvider
    from routers import stocks

    # テスト用にプロバイダーを設定（実際のAPI呼び出しはしない）
    stocks.set_providers({"JP": JQuantsProvider()})

    with TestClient(app) as client:
        yield client
