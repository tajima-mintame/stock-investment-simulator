"""自動売買: テクニカル+ファンダメンタル統合スコアリング戦略。"""

import asyncio
import logging
from datetime import date, timedelta

from database import get_db, utc_now_iso
from services.indicators import calc_ma, calc_rsi, calc_macd, calc_bollinger
from services.simulation import execute_trade, get_account_info

logger = logging.getLogger(__name__)

# 戦略パラメータ
TECH_WEIGHT = 0.70
FUND_WEIGHT = 0.30
BUY_THRESHOLD = 30
SELL_THRESHOLD = -30
MAX_POSITION_RATIO = 0.20  # 1銘柄あたり残高の20%まで


# ==========================================
# セットアップ
# ==========================================

async def setup_stocks(provider, count: int = 20) -> dict:
    """出来高上位の銘柄を自動選定・登録・同期する。"""
    stock_list = await asyncio.to_thread(provider._get_client().get_list)

    # 流動性の低い市場を除外
    stock_list = stock_list[~stock_list["MktNm"].isin(["TOKYO PRO MARKET", "その他"])]

    # プライム市場優先
    market_priority = {"プライム": 0, "スタンダード": 1, "グロース": 2}
    stock_list = stock_list.copy()
    stock_list["_priority"] = stock_list["MktNm"].map(market_priority).fillna(3)
    stock_list = stock_list.sort_values(["_priority", "Code"])

    selected = stock_list.head(count * 3)

    registered = 0
    errors = 0
    end = min(date.today(), date(2026, 1, 21))
    start = end - timedelta(days=90)

    from providers.jquants import _from_jquants_code

    for _, row in selected.iterrows():
        if registered >= count:
            break

        symbol = _from_jquants_code(row["Code"])
        name = row.get("CoName", "")
        sector = row.get("S33Nm", None)

        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO stocks (symbol, market, name, sector, currency, watched, updated_at) "
                    "VALUES (?, 'JP', ?, ?, 'JPY', 1, ?)",
                    (symbol, name, sector, utc_now_iso()),
                )
                conn.commit()

            await asyncio.sleep(0.5)
            prices = await provider.get_daily_prices(symbol, start, end)

            if len(prices) < 30:
                continue

            with get_db() as conn:
                for p in prices:
                    conn.execute(
                        "INSERT OR REPLACE INTO daily_prices "
                        "(symbol, market, date, open, high, low, close, volume, adj_close) "
                        "VALUES (?, 'JP', ?, ?, ?, ?, ?, ?, ?)",
                        (symbol, p.date.isoformat(), p.open, p.high, p.low,
                         p.close, p.volume, p.adj_close),
                    )
                conn.commit()

            # ファンダメンタルデータも取得
            await asyncio.sleep(0.3)
            try:
                jq_code = row["Code"]
                fin_df = await asyncio.to_thread(
                    provider._get_client().get_fin_summary, code=jq_code
                )
                if fin_df is not None and not fin_df.empty:
                    latest = fin_df.iloc[-1]
                    _save_fundamental(symbol, latest)
            except Exception:
                logger.debug("No fundamental data for %s", symbol)

            registered += 1
            logger.info("Registered %s (%s) with %d prices", symbol, name, len(prices))

        except Exception:
            errors += 1
            logger.exception("Failed to register %s", symbol)

    return {"registered": registered, "errors": errors}


def _save_fundamental(symbol: str, row) -> None:
    """ファンダメンタルデータをstocksテーブルのメタとしてDBに保存（簡易実装）。"""
    # 簡易的にcollection_logに保存（将来的にはfundamentalsテーブルを作る）
    eps = _safe_float(row.get("EPS"))
    feps = _safe_float(row.get("FEPS"))
    sales = _safe_float(row.get("Sales"))
    fsales = _safe_float(row.get("FSales"))
    div_ann = _safe_float(row.get("FDivAnn"))
    bps = _safe_float(row.get("BPS")) or _safe_float(row.get("NCBPS"))
    eq_ratio = _safe_float(row.get("EqAR"))

    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO collection_log (market, symbol, fetched_at, status, message) "
            "VALUES ('JP', ?, ?, 'FUNDAMENTAL', ?)",
            (symbol, utc_now_iso(),
             f"EPS={eps},FEPS={feps},Sales={sales},FSales={fsales},DivAnn={div_ann},BPS={bps},EqAR={eq_ratio}"),
        )
        conn.commit()


# ==========================================
# スコアリング戦略
# ==========================================

def run_strategy() -> dict:
    """全ウォッチリスト銘柄に対してスコアリング戦略を実行する。"""
    with get_db() as conn:
        stocks = conn.execute(
            "SELECT symbol, market FROM stocks WHERE watched = 1"
        ).fetchall()

    if not stocks:
        return {"actions": 0, "buys": 0, "sells": 0, "skipped": 0, "details": []}

    account = get_account_info()
    cash = account["cash_balance"]

    actions = 0
    buys = 0
    sells = 0
    skipped = 0
    details = []

    for s in stocks:
        symbol = s["symbol"]
        market = s["market"]

        try:
            result = _score_stock(symbol, market)
            details.append(result)

            if result["action"] == "BUY":
                qty = _calc_quantity(cash, result["price"], result["score"])
                if qty > 0:
                    execute_trade(symbol, market, "BUY", qty, result["price"])
                    buys += 1
                    actions += 1
                    cash -= qty * result["price"]
                    result["quantity"] = qty
                else:
                    result["action"] = "SKIP"
                    result["reason"] = "残高不足または投資額が小さすぎ"
                    skipped += 1
            elif result["action"] == "SELL":
                with get_db() as conn:
                    holding = conn.execute(
                        "SELECT quantity FROM portfolio_holdings WHERE symbol = ? AND market = ?",
                        (symbol, market),
                    ).fetchone()
                if holding and holding["quantity"] > 0:
                    execute_trade(symbol, market, "SELL", holding["quantity"], result["price"])
                    sells += 1
                    actions += 1
                    result["quantity"] = holding["quantity"]
                else:
                    result["action"] = "SKIP"
                    result["reason"] = "保有なし"
                    skipped += 1
            else:
                skipped += 1

        except Exception as e:
            skipped += 1
            details.append({"symbol": symbol, "action": "ERROR", "reason": str(e)})

    # 資産スナップショット保存
    _save_snapshot()

    return {"actions": actions, "buys": buys, "sells": sells, "skipped": skipped, "details": details}


def _score_stock(symbol: str, market: str) -> dict:
    """テクニカル+ファンダメンタルの統合スコアを算出する。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT date, close FROM daily_prices "
            "WHERE symbol = ? AND market = ? ORDER BY date ASC",
            (symbol, market),
        ).fetchall()

    if len(rows) < 30:
        return {"symbol": symbol, "action": "SKIP", "reason": "データ不足", "score": 0}

    dates = [date.fromisoformat(r["date"]) for r in rows]
    closes = [r["close"] for r in rows]
    latest_price = closes[-1]

    # テクニカルスコア
    tech_score = _calc_technical_score(dates, closes)

    # ファンダメンタルスコア
    fund_score = _calc_fundamental_score(symbol, latest_price)

    # 統合スコア
    total_score = tech_score * TECH_WEIGHT + fund_score * FUND_WEIGHT

    result = {
        "symbol": symbol,
        "price": latest_price,
        "tech_score": round(tech_score, 1),
        "fund_score": round(fund_score, 1),
        "score": round(total_score, 1),
    }

    if total_score > BUY_THRESHOLD:
        result["action"] = "BUY"
        result["reason"] = f"統合スコア{total_score:.0f} > {BUY_THRESHOLD}"
    elif total_score < SELL_THRESHOLD:
        result["action"] = "SELL"
        result["reason"] = f"統合スコア{total_score:.0f} < {SELL_THRESHOLD}"
    else:
        result["action"] = "HOLD"
        result["reason"] = f"統合スコア{total_score:.0f}（様子見）"

    return result


def _calc_technical_score(dates: list[date], closes: list[float]) -> float:
    """テクニカル指標からスコア(-100〜+100)を算出する。"""
    score = 0.0

    # 1. MA クロスオーバー（±30点）
    ma5 = calc_ma(dates, closes, 5)
    ma25 = calc_ma(dates, closes, 25)
    ma5_now = ma5[-1][1]
    ma5_prev = ma5[-2][1] if len(ma5) >= 2 else None
    ma25_now = ma25[-1][1]
    ma25_prev = ma25[-2][1] if len(ma25) >= 2 else None

    if ma5_now and ma25_now and ma5_prev and ma25_prev:
        if ma5_prev <= ma25_prev and ma5_now > ma25_now:
            score += 30  # ゴールデンクロス
        elif ma5_prev >= ma25_prev and ma5_now < ma25_now:
            score -= 30  # デッドクロス
        elif ma5_now > ma25_now:
            score += 10  # 上昇トレンド
        else:
            score -= 10  # 下降トレンド

    # 2. RSI（±25点）
    rsi_data = calc_rsi(dates, closes, 14)
    rsi_now = rsi_data[-1][1] if rsi_data and rsi_data[-1][1] is not None else 50
    if rsi_now < 30:
        score += 25  # 売られすぎ → 買いチャンス
    elif rsi_now < 40:
        score += 10
    elif rsi_now > 70:
        score -= 25  # 買われすぎ → 売りシグナル
    elif rsi_now > 60:
        score -= 10

    # 3. MACD（±25点）
    macd_data = calc_macd(dates, closes, 12, 26, 9)
    if macd_data:
        latest = macd_data[-1]
        prev = macd_data[-2] if len(macd_data) >= 2 else None
        _, macd_now, signal_now, hist_now = latest
        if macd_now is not None and signal_now is not None:
            if prev and prev[1] is not None and prev[2] is not None:
                # MACDがシグナルを上抜け
                if prev[1] <= prev[2] and macd_now > signal_now:
                    score += 25
                elif prev[1] >= prev[2] and macd_now < signal_now:
                    score -= 25
            if hist_now is not None:
                if hist_now > 0:
                    score += 5
                else:
                    score -= 5

    # 4. ボリンジャーバンド（±20点）
    bb_data = calc_bollinger(dates, closes, 20, 2.0)
    if bb_data:
        _, upper, middle, lower = bb_data[-1]
        if upper is not None and lower is not None:
            current = closes[-1]
            if current <= lower:
                score += 20  # 下限バンド到達 → 反発期待
            elif current >= upper:
                score -= 20  # 上限バンド到達 → 反落リスク
            elif middle is not None:
                if current > middle:
                    score += 5
                else:
                    score -= 5

    return max(-100, min(100, score))


def _calc_fundamental_score(symbol: str, price: float) -> float:
    """ファンダメンタル指標からスコア(-100〜+100)を算出する。"""
    fund = _load_fundamental(symbol)
    if fund is None:
        return 0.0  # データなしは中立

    score = 0.0

    # 1. PER（±30点）: 予想EPS ÷ 株価
    feps = fund.get("FEPS")
    if feps and feps > 0:
        per = price / feps
        if per < 10:
            score += 30  # 割安
        elif per < 15:
            score += 15
        elif per < 20:
            score += 0   # 適正
        elif per < 30:
            score -= 15
        else:
            score -= 30  # 割高

    # 2. 配当利回り（±25点）
    div = fund.get("DivAnn")
    if div and div > 0 and price > 0:
        yield_pct = (div / price) * 100
        if yield_pct > 4:
            score += 25  # 高配当
        elif yield_pct > 3:
            score += 15
        elif yield_pct > 2:
            score += 5
        elif yield_pct < 0.5:
            score -= 10

    # 3. 売上成長率（±25点）
    sales = fund.get("Sales")
    fsales = fund.get("FSales")
    if sales and fsales and sales > 0:
        growth = (fsales - sales) / sales
        if growth > 0.15:
            score += 25  # 高成長
        elif growth > 0.05:
            score += 10
        elif growth < -0.05:
            score -= 15
        elif growth < -0.15:
            score -= 25

    # 4. 自己資本比率（±20点）
    eq_ratio = fund.get("EqAR")
    if eq_ratio:
        if eq_ratio > 0.5:
            score += 20  # 財務健全
        elif eq_ratio > 0.3:
            score += 10
        elif eq_ratio < 0.15:
            score -= 20  # 財務リスク

    return max(-100, min(100, score))


def _load_fundamental(symbol: str) -> dict | None:
    """collection_logからファンダメンタルデータを読み込む。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT message FROM collection_log "
            "WHERE symbol = ? AND status = 'FUNDAMENTAL' "
            "ORDER BY fetched_at DESC LIMIT 1",
            (symbol,),
        ).fetchone()

    if row is None:
        return None

    # パース: "EPS=136.07,FEPS=224.81,Sales=24630753000000,..."
    data = {}
    for pair in row["message"].split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            data[k] = _safe_float(v)

    return data


# ==========================================
# ユーティリティ
# ==========================================

def _calc_quantity(cash: float, price: float, score: float) -> int:
    """スコアに応じた投資額で購入数量を計算する。"""
    if price <= 0:
        return 0
    # スコアが高いほど多く投資（最大MAX_POSITION_RATIO）
    score_factor = min(abs(score) / 100, 1.0)
    max_amount = cash * MAX_POSITION_RATIO * score_factor
    return max(int(max_amount / price), 0)


def _save_snapshot() -> None:
    """現在の資産状況をスナップショットとして保存する。"""
    info = get_account_info()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO asset_snapshots (timestamp, cash, portfolio, total) "
            "VALUES (?, ?, ?, ?)",
            (utc_now_iso(), info["cash_balance"], info["portfolio_value"], info["total_value"]),
        )
        conn.commit()


def _safe_float(v) -> float | None:
    """安全にfloatに変換する。"""
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def get_rankings(sort_by: str = "score", limit: int = 10) -> list[dict]:
    """全登録銘柄のスコアランキングを返す。"""
    with get_db() as conn:
        stocks = conn.execute(
            "SELECT symbol, market, name, sector FROM stocks WHERE watched = 1"
        ).fetchall()

    if not stocks:
        return []

    rankings = []
    for s in stocks:
        result = _score_stock(s["symbol"], s["market"])
        if result.get("action") == "SKIP" and result.get("reason") == "データ不足":
            continue
        result["name"] = s["name"]
        result["sector"] = s["sector"]
        rankings.append(result)

    key_map = {
        "score": lambda r: r.get("score", 0),
        "tech_score": lambda r: r.get("tech_score", 0),
        "fund_score": lambda r: r.get("fund_score", 0),
    }
    key_fn = key_map.get(sort_by, key_map["score"])
    rankings.sort(key=key_fn, reverse=True)

    return rankings[:limit]


def toggle_auto_trade(enabled: bool, provider=None) -> dict:
    """自動取引のON/OFFを切り替える。ONで即時セットアップ+実行。"""
    if not enabled:
        # OFF: ウォッチリスト全解除
        with get_db() as conn:
            conn.execute("UPDATE stocks SET watched = 0")
            conn.commit()
        return {"enabled": False, "message": "自動取引を停止しました"}

    # ON: 既にウォッチ銘柄があればそのまま実行、なければ返すだけ
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM stocks WHERE watched = 1").fetchone()[0]

    if count == 0:
        return {"enabled": True, "message": "銘柄が未登録です。自動売買画面からセットアップしてください", "need_setup": True}

    result = run_strategy()
    return {"enabled": True, "message": f"実行完了: 買い{result['buys']}件 / 売り{result['sells']}件", "run": result}


def get_auto_trade_results() -> dict:
    """自動売買の結果を集計する。"""
    with get_db() as conn:
        trades = conn.execute(
            "SELECT symbol, market, side, quantity, price, executed_at "
            "FROM trades ORDER BY executed_at ASC"
        ).fetchall()

        holdings = conn.execute(
            "SELECT h.symbol, h.market, h.quantity, h.avg_cost, s.name "
            "FROM portfolio_holdings h "
            "LEFT JOIN stocks s ON h.symbol = s.symbol AND h.market = s.market"
        ).fetchall()

        snapshots = conn.execute(
            "SELECT timestamp, total FROM asset_snapshots ORDER BY timestamp ASC"
        ).fetchall()

    # 銘柄ごとの損益集計
    stock_results: dict[str, dict] = {}
    positions: dict[str, list[tuple[int, float]]] = {}

    for t in trades:
        symbol = t["symbol"]
        if symbol not in stock_results:
            stock_results[symbol] = {
                "symbol": symbol,
                "buy_count": 0, "sell_count": 0,
                "total_buy": 0.0, "total_sell": 0.0,
                "realized_pnl": 0.0,
            }
        r = stock_results[symbol]
        if t["side"] == "BUY":
            r["buy_count"] += 1
            r["total_buy"] += t["quantity"] * t["price"]
            positions.setdefault(symbol, []).append((t["quantity"], t["price"]))
        else:
            r["sell_count"] += 1
            r["total_sell"] += t["quantity"] * t["price"]
            remaining = t["quantity"]
            sell_price = t["price"]
            lots = positions.get(symbol, [])
            while remaining > 0 and lots:
                lot_qty, lot_price = lots[0]
                matched = min(remaining, lot_qty)
                r["realized_pnl"] += matched * (sell_price - lot_price)
                remaining -= matched
                if matched == lot_qty:
                    lots.pop(0)
                else:
                    lots[0] = (lot_qty - matched, lot_price)

    results = list(stock_results.values())
    for r in results:
        r["status"] = "利益" if r["realized_pnl"] > 0 else ("損失" if r["realized_pnl"] < 0 else "未確定")

    # サマリー
    total_pnl = sum(r["realized_pnl"] for r in results)
    closed = [r for r in results if r["sell_count"] > 0]
    wins = [r for r in closed if r["realized_pnl"] > 0]
    losses = [r for r in closed if r["realized_pnl"] <= 0]

    account = get_account_info()

    return {
        "summary": {
            "total_stocks": len(results),
            "total_pnl": total_pnl,
            "win_count": len(wins),
            "lose_count": len(losses),
            "win_rate": len(wins) / len(closed) if closed else 0.0,
            "current_total": account["total_value"],
            "initial_balance": 100000.0,
            "return_pct": (account["total_value"] - 100000.0) / 100000.0,
        },
        "results": sorted(results, key=lambda r: r["realized_pnl"], reverse=True),
        "snapshots": [{"timestamp": s["timestamp"], "total": s["total"]} for s in snapshots],
    }
