# リポジトリルール: stock-investment-simulator

## 概要
株式投資シミュレーター。日本株（東証）と米国株の仮想売買を行うWebアプリケーション。

## 技術スタック
- バックエンド: Python 3.12+ / FastAPI
- フロントエンド: Plain HTML/JS（ビルドステップなし）
- DB: SQLite（sqlite3標準ライブラリ、ORM不使用）
- チャート: TradingView Lightweight Charts v4（CDN）
- 日本株API: J-Quants API V2
- 米国株API: Finnhub

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

### テスト実行
```bash
cd backend && python -m pytest -v
```

### 脆弱性チェック
```bash
cd backend && pip audit
```

## コーディング規約
- DB操作: パラメータ化クエリを必ず使用（SQLインジェクション防止）
- APIキー: `.env`から読み込み、コードにハードコードしない
- エラーメッセージ: 内部情報を含めない
- 外部APIレスポンス: 必ずバリデーションする

## ディレクトリ構成
- `backend/` — FastAPI バックエンド
- `frontend/` — 静的ファイル（FastAPI StaticFilesで配信）
- `data/` — SQLiteデータベース（.gitignore対象）
