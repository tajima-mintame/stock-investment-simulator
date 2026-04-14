# リポジトリルール: stock-investment-simulator

このファイルはグローバルルール（`~/.claude/CLAUDE.md`）の原則を、本リポジトリの技術スタックで具体化したものである。

## 概要

株式投資シミュレーター。日本株（東証）の仮想売買を行うWebアプリケーション。
米国株（Finnhub）は将来対応予定。プロバイダー抽象化とDBスキーマは対応済み。

## 技術スタック

- バックエンド: Python 3.12+ / FastAPI
- フロントエンド: Plain HTML/JS（ビルドステップなし）
- DB: SQLite（sqlite3標準ライブラリ、ORM不使用）
- チャート: TradingView Lightweight Charts v4（CDN）
- 日本株API: J-Quants API V2
- 米国株API: Finnhub（将来対応予定）

## 開発コマンド

### 環境セットアップ

```bash
cd backend && pip install -r requirements.txt
cp .env.example .env  # APIキーを設定
```

### サーバー起動

```bash
cd backend && uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### テスト実行（UT / IT）

```bash
cd backend && python -m pytest -v
```

### 脆弱性チェック

```bash
pip audit -r backend/requirements.txt
```

### lint / format

```bash
cd backend && python -m ruff check . && python -m ruff format --check .
```

## 品質検証プロセス（グローバルルール準拠）

コード変更後は以下を順に実施する。

| レベル | 実行方法 | 確認内容 |
|--------|---------|---------|
| UT（単体テスト） | `cd backend && python -m pytest tests/ -v` | services/, providers/ の関数単位の動作 |
| IT（結合テスト） | `cd backend && python -m pytest tests/ -v -m integration` | FastAPI TestClient でAPIエンドポイント間の連携 |
| ST（システムテスト） | `uvicorn main:app` → ブラウザで操作 | 画面操作で機能全体が期待通り動作すること |

## CI（グローバルルール準拠）

push / pull_request で以下を実行する構成にする。

1. `pip install -r backend/requirements.txt`
2. `cd backend && python -m ruff check .`
3. `cd backend && python -m pytest -v`
4. `pip audit -r backend/requirements.txt`

## 依存パッケージ（グローバルルール準拠）

パッケージ追加後は必ず以下を実施する。

```bash
pip audit -r backend/requirements.txt
```

高リスク脆弱性が検出された場合は、対応方針（アップグレード / 代替ライブラリ / リスク受容）を決めてからコミットする。

## コーディング規約

### セキュリティ（グローバルルール準拠）

- DB操作: パラメータ化クエリを必ず使用（SQLインジェクション防止）
- APIキー: `.env` から読み込み、コードにハードコードしない
- `.env` や秘密情報は絶対にコミットしない（`.env.example` のみ共有）
- エラーメッセージ: 内部情報（スタックトレース、DBスキーマ等）を含めない
- 外部APIレスポンス: 型・値を必ずバリデーションしてからDBに保存する

### コミット（グローバルルール準拠）

- Conventional Commits でメッセージを書く（例: `feat(trade): add virtual trading endpoint`）
- デバッグコードはコミット前に削除する
- テストなしで機能を追加しない
- 動作が壊れた状態でコミットしない

## ディレクトリ構成

```
stock-investment-simulator/
├── backend/          — FastAPI バックエンド
│   ├── providers/    — 外部API抽象化（MarketDataProvider）
│   ├── routers/      — APIエンドポイント
│   ├── services/     — ビジネスロジック（指標計算、損益計算等）
│   └── tasks/        — バックグラウンド処理
├── frontend/         — 静的ファイル（FastAPI StaticFilesで配信）
│   └── js/
│       ├── pages/    — 各画面（dashboard, stock-detail, trading等）
│       └── components/ — 共通コンポーネント（chart, table）
├── docs/             — 要件定義書・設計書
├── data/             — SQLiteデータベース（.gitignore対象）
└── CLAUDE.md         — このファイル
```

## GitHub Projects

- プロジェクト: [Stock Investment Simulator](https://github.com/users/tajima-mintame/projects/9)
- リポジトリ: [tajima-mintame/stock-investment-simulator](https://github.com/tajima-mintame/stock-investment-simulator)

Issue作成・フィールド設定・作業ログ記録はグローバルルールの「チケット運用ルール」「Issue作成チェックリスト」に従う。
