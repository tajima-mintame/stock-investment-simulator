# 設計書: 株式投資シミュレーター

## 1. システム構成

### 1.1 技術スタック

| レイヤー | 技術 | 選定理由 |
|---------|------|---------|
| バックエンド | Python 3.12+ / FastAPI | データ分析ライブラリ（pandas等）との親和性が高い |
| フロントエンド | Plain HTML/JS（ビルドステップなし） | 学習プロジェクトにReactは過剰。CDNで依存を管理 |
| チャート | TradingView Lightweight Charts v4 | 金融チャート専用。40KB。OSS |
| DB | SQLite（sqlite3標準ライブラリ） | 6テーブルの規模にORMは不要。パラメータ化クエリで直接操作 |
| 日本株API | J-Quants API V2 | 東証データの唯一の公式無料ソース |
| 米国株API（将来） | Finnhub | 無料枠が最も充実（60 req/min）。初期リリースでは未使用 |
| バックグラウンド処理 | APScheduler AsyncIOScheduler | FastAPIプロセス内で動作。外部ワーカー不要 |
| HTTPクライアント | httpx（async） | 将来の外部API直接呼び出し用。J-Quantsはsync→asyncio.to_thread() |

### 1.2 アーキテクチャ概要

```
┌──────────────────┐
│   Browser        │
│  (Frontend)      │
└────────┬─────────┘
         │ HTTP (fetch)
┌────────▼─────────┐
│   FastAPI         │
│   Backend         │
├───────────────────┤
│  Routers          │──► Services (indicators, simulation, screening, portfolio)
│  (REST API)       │
└────────┬──────────┘
         │
    ┌────┼─────────────┐
    │    │             │
┌───▼──┐ │    ┌────────▼───────┐
│SQLite│ │    │  APScheduler   │
│(read)│ │    │  (background)  │
└──────┘ │    └────────┬───────┘
         │             │
    ┌────▼─────┐       │
    │Providers │◄──────┘
    │(unified) │
    ├────┴─────┤
    │          │
┌───▼────┐ ┌──▼───┐
│J-Quants│ │(将来)│
│ API V2 │ │Finnhub│
└────────┘ └──────┘
```

- フロントエンドはFastAPIの `StaticFiles` で配信（CORS不要）
- 全データはSQLiteに永続化
- 外部APIアクセスはProviderレイヤーで抽象化（`MarketDataProvider` インターフェース）
- 初期リリースではJ-Quants（日本株）のみ。米国株は将来フェーズで `FinnhubProvider` を追加予定

## 2. ディレクトリ構成

```
stock-investment-simulator/
├── backend/
│   ├── main.py                    # FastAPIエントリポイント（lifespan, ルーター登録, 静的配信）
│   ├── config.py                  # 環境変数読み込み（APIキー, DBパス, サーバー設定）
│   ├── database.py                # SQLite接続管理, スキーマ定義, init_db()
│   ├── models.py                  # Pydanticリクエスト/レスポンスモデル
│   ├── providers/
│   │   ├── base.py                # MarketDataProvider 抽象基底クラス
│   │   └── jquants.py             # J-Quants V2ラッパー（東証）
│   ├── routers/
│   │   ├── stocks.py              # 株価・銘柄情報エンドポイント
│   │   ├── trades.py              # 仮想売買エンドポイント
│   │   ├── portfolio.py           # ポートフォリオ分析エンドポイント
│   │   └── screening.py           # 銘柄スクリーニングエンドポイント
│   ├── services/
│   │   ├── indicators.py          # テクニカル指標計算（MA, RSI, MACD, BB）
│   │   ├── simulation.py          # 損益計算、勝率、リスクリターン
│   │   ├── screening.py           # フィルタリングロジック
│   │   └── portfolio.py           # 配分計算、相関分析
│   ├── tasks/
│   │   └── collector.py           # バックグラウンドデータ収集
│   └── requirements.txt
├── frontend/
│   ├── index.html                 # SPAシェル
│   ├── style.css                  # ダークテーマUI
│   └── js/
│       ├── app.js                 # ハッシュルーター
│       ├── api.js                 # バックエンドAPIクライアント
│       ├── pages/
│       │   ├── dashboard.js       # ダッシュボード
│       │   ├── stock-detail.js    # 銘柄詳細（チャート + 売買）
│       │   ├── trading.js         # 取引履歴 + 損益統計
│       │   ├── portfolio.js       # ポートフォリオ分析
│       │   └── screening.js       # 銘柄スクリーニング
│       └── components/
│           ├── chart.js           # Lightweight Chartsラッパー
│           └── table.js           # 汎用テーブルコンポーネント
├── docs/                          # ドキュメント
├── data/                          # SQLiteデータベース（.gitignore対象）
├── .env.example                   # 環境変数テンプレート
├── .gitignore
└── CLAUDE.md                      # リポジトリルール
```

## 3. データベース設計

### 3.1 ER図

```
┌─────────────┐       ┌──────────────┐
│   stocks    │       │ daily_prices │
├─────────────┤       ├──────────────┤
│*symbol  PK  │◄──┐   │*symbol  PK,FK│
│*market  PK  │   ├───│*market  PK,FK│
│ name        │   │   │*date    PK   │
│ sector      │   │   │ open         │
│ currency    │   │   │ high         │
│ updated_at  │   │   │ low          │
└─────────────┘   │   │ close        │
                  │   │ volume       │
                  │   │ adj_close    │
                  │   └──────────────┘
                  │
                  │   ┌──────────────────┐
                  │   │     trades       │
                  │   ├──────────────────┤
                  │   │ id      PK (AUTO)│
                  ├───│ symbol  FK       │
                  │   │ market  FK       │
                  │   │ side             │
                  │   │ quantity         │
                  │   │ price            │
                  │   │ executed_at      │
                  │   │ note             │
                  │   └──────────────────┘
                  │
                  │   ┌──────────────────────┐
                  │   │ portfolio_holdings   │
                  │   ├──────────────────────┤
                  └───│*symbol  PK,FK        │
                      │*market  PK,FK        │
                      │ quantity             │
                      │ avg_cost             │
                      └──────────────────────┘

┌──────────────────┐   ┌──────────────────┐
│    account       │   │ collection_log   │
├──────────────────┤   ├──────────────────┤
│ id  PK (=1)      │   │ id    PK (AUTO)  │
│ cash_balance     │   │ market           │
│ created_at       │   │ symbol           │
└──────────────────┘   │ fetched_at       │
                       │ status           │
                       │ message          │
                       └──────────────────┘
```

### 3.2 テーブル定義

#### stocks（銘柄マスタ）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| symbol | TEXT | PK | 銘柄コード（例: "7203"） |
| market | TEXT | PK | 市場区分（初期は "JP" のみ。将来 "US" を追加予定） |
| name | TEXT | | 企業名 |
| sector | TEXT | | セクター |
| currency | TEXT | DEFAULT 'JPY' | 通貨 |
| updated_at | TEXT | | 最終更新日時（ISO8601） |

複合主キー `(symbol, market)` により、日本株コード "7203" と米国ティッカーの衝突を回避する。

#### daily_prices（日足価格）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| symbol | TEXT | PK, FK | 銘柄コード |
| market | TEXT | PK, FK | 市場区分 |
| date | TEXT | PK | 日付（YYYY-MM-DD） |
| open | REAL | | 始値 |
| high | REAL | | 高値 |
| low | REAL | | 安値 |
| close | REAL | | 終値 |
| volume | INTEGER | | 出来高 |
| adj_close | REAL | | 調整後終値（株式分割・配当考慮） |

インデックス:
- `idx_prices_date` — 日付での範囲検索用
- `idx_prices_symbol_date` — 銘柄+日付の複合検索用

日付を TEXT 型（ISO8601）で保存する理由: クエリは日付範囲ベースであり、SQLiteはISO8601文字列の比較を正しく処理する。

#### trades（取引履歴）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | INTEGER | PK AUTOINCREMENT | 取引ID |
| symbol | TEXT | FK | 銘柄コード |
| market | TEXT | FK | 市場区分 |
| side | TEXT | NOT NULL | 売買区分（"BUY" or "SELL"） |
| quantity | INTEGER | NOT NULL | 数量 |
| price | REAL | NOT NULL | 約定価格 |
| executed_at | TEXT | NOT NULL | 約定日時（ISO8601） |
| note | TEXT | | メモ |

#### portfolio_holdings（保有銘柄）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| symbol | TEXT | PK, FK | 銘柄コード |
| market | TEXT | PK, FK | 市場区分 |
| quantity | INTEGER | NOT NULL | 保有数量 |
| avg_cost | REAL | NOT NULL | 平均取得単価 |

取引のたびに更新されるマテリアライズドビュー。損益はtradesテーブルから直接計算する。

#### account（仮想口座）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | INTEGER | PK, CHECK(id=1) | シングルトン制約 |
| cash_balance | REAL | NOT NULL, DEFAULT 100000 | 現金残高（JPY、初期10万円） |
| created_at | TEXT | NOT NULL | 作成日時 |

`CHECK (id = 1)` により、テーブルには常に1行のみ存在する。

#### collection_log（収集ログ）

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| id | INTEGER | PK AUTOINCREMENT | ログID |
| market | TEXT | NOT NULL | 市場区分 |
| symbol | TEXT | | 銘柄（NULLは全銘柄一括） |
| fetched_at | TEXT | NOT NULL | 取得日時 |
| status | TEXT | NOT NULL | 結果（"OK" or "ERROR"） |
| message | TEXT | | 詳細メッセージ |

### 3.3 SQLite設定

- `PRAGMA journal_mode=WAL` — 読み書きの並行性を向上
- `PRAGMA foreign_keys=ON` — 外部キー制約を有効化

## 4. API設計

### 4.1 株価・市場データ

| メソッド | パス | 説明 | レスポンス |
|----------|------|------|-----------|
| GET | `/api/stocks` | 登録銘柄一覧 | StockListResponse |
| GET | `/api/stocks/search` | 外部API銘柄検索 | StockInfo[] |
| GET | `/api/stocks/{market}/{symbol}` | 銘柄詳細 + 最新価格 | StockDetail |
| GET | `/api/stocks/{market}/{symbol}/prices` | 日足OHLCV | PriceListResponse |
| GET | `/api/stocks/{market}/{symbol}/indicators` | テクニカル指標 | IndicatorsResponse |
| POST | `/api/stocks/sync` | 外部APIからデータ取得→DB保存 | SyncResponse |

`GET /api/stocks` クエリパラメータ:
- `market` (string, optional): "JP" or "US"
- `sector` (string, optional): セクター名
- `q` (string, optional): 銘柄コードまたは名前で部分一致検索

`GET /api/stocks/{market}/{symbol}/prices` クエリパラメータ:
- `from` (date, optional): 開始日
- `to` (date, optional): 終了日

`GET /api/stocks/{market}/{symbol}/indicators` クエリパラメータ:
- `type` (string): カンマ区切り（"ma,rsi,macd,bb"）
- `period` (int): 期間（デフォルト20）

`POST /api/stocks/sync` リクエストボディ:
```json
{
  "symbol": "7203",
  "market": "JP",
  "from_date": "2024-01-01",
  "to_date": "2026-04-15"
}
```

### 4.2 仮想売買

| メソッド | パス | 説明 | レスポンス |
|----------|------|------|-----------|
| GET | `/api/account` | 残高 + ポートフォリオ総額 | AccountInfo |
| POST | `/api/trades` | 仮想取引実行 | TradeRecord |
| GET | `/api/trades` | 取引履歴 | TradeRecord[] |
| GET | `/api/trades/stats` | 損益統計 | TradeStats |

`POST /api/trades` リクエストボディ:
```json
{
  "symbol": "7203",
  "market": "JP",
  "side": "BUY",
  "quantity": 100,
  "price": 2850.0,
  "note": "トヨタ買い"
}
```

### 4.3 ポートフォリオ

| メソッド | パス | 説明 | レスポンス |
|----------|------|------|-----------|
| GET | `/api/portfolio` | 保有銘柄 + 含み損益 | PortfolioResponse |
| GET | `/api/portfolio/allocation` | セクター/市場別配分 | AllocationResponse |
| GET | `/api/portfolio/correlation` | 相関行列 | float[][] |

### 4.4 スクリーニング

| メソッド | パス | 説明 | レスポンス |
|----------|------|------|-----------|
| GET | `/api/screening` | 条件フィルタ | ScreeningResult[] |

クエリパラメータ:
- `market` (string, optional)
- `min_volume` (int, optional)
- `max_volume` (int, optional)
- `min_volatility` (float, optional)
- `max_volatility` (float, optional)
- `sort_by` (string, optional): "volume", "volatility", "change_pct"

### 4.5 システム

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/health` | ヘルスチェック |
| GET | `/api/collection/status` | 直近の収集状態 |

## 5. プロバイダー設計

### 5.1 抽象インターフェース

```python
class MarketDataProvider(ABC):
    async def get_stock_info(self, symbol: str) -> StockData | None
    async def get_daily_prices(self, symbol: str, start: date, end: date) -> list[PriceData]
    async def search_stocks(self, query: str) -> list[StockData]
```

全プロバイダーはこのインターフェースに準拠する。ルーターは市場区分をキーにプロバイダーを切り替える。初期リリースでは "JP" のみ登録。米国株対応時に "US" キーで `FinnhubProvider` を追加する。

### 5.2 J-Quants プロバイダー

- ライブラリ: `jquants-api-client` (sync)
- async化: `asyncio.to_thread()` でsync呼び出しをラップ
- 銘柄情報: `get_listed_info()` → Code で検索
- 日足データ: `get_prices_daily_quotes(code, from_yyyymmdd, to_yyyymmdd)`
- 調整後終値: `AdjustmentClose` フィールド対応

### 5.3 Finnhub プロバイダー（将来対応予定）

米国株対応時に `backend/providers/finnhub.py` として実装する。

- HTTPクライアント: `httpx.AsyncClient`
- レート制限: `asyncio.Semaphore(30)` で30 req/sec に制御
- 銘柄情報: `GET /stock/profile2`
- 日足データ: `GET /stock/candle` （UNIXタイムスタンプで期間指定、resolution=D）
- 銘柄検索: `GET /search` （Common Stock / EQS のみフィルタ）

## 6. フロントエンド設計

### 6.1 画面構成

単一 `index.html` + ハッシュルーティング。ES Modules で各ページを分離。

| 画面 | ハッシュ | 機能 |
|------|---------|------|
| ダッシュボード | `#/` | 口座サマリー、データ同期フォーム、登録銘柄一覧 |
| 銘柄詳細 | `#/stock/{market}/{symbol}` | 銘柄情報、ローソク足チャート、テクニカル指標、売買ボタン |
| 取引 | `#/trading` | 取引フォーム、取引履歴テーブル、損益統計カード |
| ポートフォリオ | `#/portfolio` | 保有一覧、セクター配分円グラフ、相関ヒートマップ |
| スクリーニング | `#/screening` | フィルタフォーム、結果テーブル |

### 6.2 外部ライブラリ（CDN読み込み）

| ライブラリ | バージョン | 用途 |
|-----------|----------|------|
| Lightweight Charts | v4.2.2 | ローソク足チャート、出来高ヒストグラム、ラインチャート |

### 6.3 UIデザイン方針

- ダークテーマ（背景: `#0f1117`, カード: `#1a1d29`）
- CSS変数で色を一元管理
- レスポンシブ対応（768px以下でグリッドを1カラムに）
- 上昇: 緑 (`#22c55e`)、下落: 赤 (`#ef4444`)

## 7. バックグラウンド処理設計

### 7.1 定期データ収集

APScheduler `AsyncIOScheduler` をFastAPIのlifespanイベントで起動する。

| スケジュール | 対象 | トリガー |
|-------------|------|---------|
| 平日 16:00 JST | 日本株（全登録銘柄） | TSE 15:30 閉場後 |

米国株対応時には `平日 22:00 JST`（NYSE/NASDAQ 閉場後）のスケジュールを追加する。

各実行で:
1. `stocks` テーブルの登録銘柄を取得
2. 各銘柄の最新日付以降のデータを外部APIから取得
3. `daily_prices` に UPSERT
4. `collection_log` に結果を記録

## 8. 実装フェーズ

| Phase | 内容 | 主要成果物 |
|-------|------|-----------|
| 1 | 基盤構築 | プロジェクト構造、DB、プロバイダー、株価API、フロントエンド最小構成 |
| 2 | 仮想売買 | 取引API、損益計算、取引画面、銘柄詳細に売買ボタン |
| 3 | テクニカル分析 | MA/RSI/MACD/BB計算、チャートオーバーレイ |
| 4 | スクリーニング + ポートフォリオ | スクリーニング画面、ポートフォリオ分析画面 |
| 5 | バックグラウンド収集 + 仕上げ | APScheduler、ウォッチリスト、UI仕上げ |

## 9. テスト方針

各フェーズ完了時に以下を実施する。

| レベル | ツール | 対象 |
|--------|-------|------|
| UT（単体テスト） | pytest | services/, providers/ の関数単位 |
| IT（結合テスト） | FastAPI TestClient | APIエンドポイント間の連携 |
| ST（システムテスト） | uvicorn + ブラウザ | 画面操作による機能全体の確認 |
