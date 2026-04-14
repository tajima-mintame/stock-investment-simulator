import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH, INITIAL_BALANCE

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    name        TEXT,
    sector      TEXT,
    currency    TEXT DEFAULT 'JPY',
    updated_at  TEXT,
    PRIMARY KEY (symbol, market)
);

CREATE TABLE IF NOT EXISTS daily_prices (
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    date        TEXT NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      INTEGER,
    adj_close   REAL,
    PRIMARY KEY (symbol, market, date),
    FOREIGN KEY (symbol, market) REFERENCES stocks(symbol, market)
);

CREATE INDEX IF NOT EXISTS idx_prices_date ON daily_prices(date);
CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON daily_prices(symbol, market, date);

CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    side        TEXT NOT NULL,
    quantity    INTEGER NOT NULL,
    price       REAL NOT NULL,
    executed_at TEXT NOT NULL,
    note        TEXT,
    FOREIGN KEY (symbol, market) REFERENCES stocks(symbol, market)
);

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    symbol      TEXT NOT NULL,
    market      TEXT NOT NULL,
    quantity    INTEGER NOT NULL,
    avg_cost    REAL NOT NULL,
    PRIMARY KEY (symbol, market),
    FOREIGN KEY (symbol, market) REFERENCES stocks(symbol, market)
);

CREATE TABLE IF NOT EXISTS account (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    cash_balance    REAL NOT NULL DEFAULT 100000,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    market      TEXT NOT NULL,
    symbol      TEXT,
    fetched_at  TEXT NOT NULL,
    status      TEXT NOT NULL,
    message     TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    """SQLite接続を取得する。row_factoryをRow に設定済み。"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """テーブル作成とアカウント初期化を実行する。"""
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        # アカウントが未作成なら初期残高で作成
        row = conn.execute("SELECT id FROM account WHERE id = 1").fetchone()
        if row is None:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO account (id, cash_balance, created_at) VALUES (1, ?, ?)",
                (INITIAL_BALANCE, now),
            )
        conn.commit()
    finally:
        conn.close()
