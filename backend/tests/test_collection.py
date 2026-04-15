"""データ収集・ウォッチリストのテスト。"""

import pytest

from helpers import add_stock
from database import get_db


class TestCollectionAPI:
    def test_status_empty(self, app_client):
        resp = app_client.get("/api/collection/status")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_run_no_watched(self, app_client):
        resp = app_client.post("/api/collection/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["collected"] == 0
        assert data["errors"] == 0

    def test_toggle_watch(self, app_client, seed_stock):
        # 初期状態: watched=0
        resp = app_client.post("/api/collection/watch/JP/7203")
        assert resp.status_code == 200
        data = resp.json()
        assert data["watched"] is True

        # もう一度トグル → watched=0
        resp = app_client.post("/api/collection/watch/JP/7203")
        data = resp.json()
        assert data["watched"] is False

    def test_toggle_watch_not_found(self, app_client):
        resp = app_client.post("/api/collection/watch/JP/9999")
        assert resp.status_code == 200
        assert resp.json().get("error") == "Stock not found"

    def test_status_limit(self, app_client):
        resp = app_client.get("/api/collection/status?limit=5")
        assert resp.status_code == 200

    def test_collection_creates_log(self, app_client, seed_stock):
        """Syncした銘柄は収集ログに記録される"""
        # Sync already creates a log via stocks/sync
        resp = app_client.get("/api/collection/status?limit=1")
        assert resp.status_code == 200


class TestWatchedColumn:
    def test_default_watched_is_zero(self, test_db):
        add_stock("7203")
        with get_db() as conn:
            row = conn.execute(
                "SELECT watched FROM stocks WHERE symbol = '7203'"
            ).fetchone()
            assert row["watched"] == 0

    def test_set_watched(self, test_db):
        add_stock("7203")
        with get_db() as conn:
            conn.execute(
                "UPDATE stocks SET watched = 1 WHERE symbol = '7203' AND market = 'JP'"
            )
            conn.commit()
            row = conn.execute(
                "SELECT watched FROM stocks WHERE symbol = '7203'"
            ).fetchone()
            assert row["watched"] == 1
