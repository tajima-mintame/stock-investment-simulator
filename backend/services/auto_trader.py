"""自動売買: 銘柄自動選定・テクニカル戦略による売買・結果集計。"""

import logging
from datetime import date, timedelta

from database import get_db, utc_now_iso
from services.indicators import calc_ma, calc_rsi
from services.simulation import execute_trade, get_account_info

logger = logging.getLogger(__name__)

# 1銘柄あたりの最大投資比率（残高の何%まで）
MAX_POSITION_RATIO = 0.15


async def setup_stocks(provider, count: int = 20) -> dict:
    """出来高上位の銘柄を自動選定・登録・同期する。"""
    import asyncio

    # 全上場銘柄リストを取得
    stock_list = await asyncio.to_thread(provider._get_client().get_list)

    # TOKYO PRO MARKET を除外（流動性が低い）
    stock_list = stock_list[stock_list["MktNm"] != "TOKYO PRO MARKET"]
    stock_list = stock_list[stock_list["MktNm"] != "その他"]

    # ランダムに偏らないよう、コードでソートしてから選定
    # 出来高は日足データ取得後に判断するため、まずプライム→スタンダード→グロースの順で選定
    market_priority = {"プライム": 0, "スタンダード": 1, "グロース": 2}
    stock_list = stock_list.copy()
    stock_list["_priority"] = stock_list["MktNm"].map(market_priority).fillna(3)
    stock_list = stock_list.sort_values(["_priority", "Code"])

    # 上位N銘柄を選定
    selected = stock_list.head(count * 2)  # 余裕を持って取得

    registered = 0
    errors = 0

    # J-Quants無料プランの日付制限に対応: 利用可能範囲内で直近データを取得
    end = min(date.today(), date(2026, 1, 21))  # 無料プラン上限
    start = end - timedelta(days=90)

    from providers.jquants import _from_jquants_code

    for _, row in selected.iterrows():
        if registered >= count:
            break

        symbol = _from_jquants_code(row["Code"])
        name = row.get("CoName", "")
        sector = row.get("S33Nm", None)

        try:
            # DB登録
            with get_db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO stocks (symbol, market, name, sector, currency, watched, updated_at) "
                    "VALUES (?, 'JP', ?, ?, 'JPY', 1, ?)",
                    (symbol, name, sector, utc_now_iso()),
                )
                conn.commit()

            # レート制限対策: リクエスト間に待機
            import asyncio
            await asyncio.sleep(0.5)

            # 日足データ同期
            prices = await provider.get_daily_prices(symbol, start, end)

            if len(prices) < 30:
                # データ不足の銘柄はスキップ
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

            registered += 1
            logger.info("Registered %s (%s) with %d prices", symbol, name, len(prices))

        except Exception:
            errors += 1
            logger.exception("Failed to register %s", symbol)

    return {"registered": registered, "errors": errors}


def run_strategy() -> dict:
    """全登録銘柄に対してMA/RSI戦略を実行する。"""
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
            result = _evaluate_stock(symbol, market, cash)
            details.append(result)

            if result["action"] == "BUY":
                qty = _calc_quantity(cash, result["price"])
                if qty > 0:
                    execute_trade(symbol, market, "BUY", qty, result["price"])
                    buys += 1
                    actions += 1
                    cash -= qty * result["price"]
                    result["quantity"] = qty
                else:
                    result["action"] = "SKIP"
                    result["reason"] = "残高不足"
                    skipped += 1

            elif result["action"] == "SELL":
                # 保有している場合のみ売り
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
            details.append({
                "symbol": symbol,
                "action": "ERROR",
                "reason": str(e),
            })

    return {
        "actions": actions,
        "buys": buys,
        "sells": sells,
        "skipped": skipped,
        "details": details,
    }


def _evaluate_stock(symbol: str, market: str, cash: float) -> dict:
    """1銘柄のMA/RSI戦略を評価する。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT date, close FROM daily_prices "
            "WHERE symbol = ? AND market = ? ORDER BY date ASC",
            (symbol, market),
        ).fetchall()

    if len(rows) < 30:
        return {"symbol": symbol, "action": "SKIP", "reason": "データ不足"}

    dates = [date.fromisoformat(r["date"]) for r in rows]
    closes = [r["close"] for r in rows]
    latest_price = closes[-1]

    # MA計算
    ma5 = calc_ma(dates, closes, 5)
    ma25 = calc_ma(dates, closes, 25)

    # RSI計算
    rsi_data = calc_rsi(dates, closes, 14)

    # 最新のMA値
    ma5_now = ma5[-1][1]
    ma5_prev = ma5[-2][1] if len(ma5) >= 2 else None
    ma25_now = ma25[-1][1]
    ma25_prev = ma25[-2][1] if len(ma25) >= 2 else None

    # 最新のRSI値
    rsi_now = rsi_data[-1][1] if rsi_data else None

    if ma5_now is None or ma25_now is None or ma5_prev is None or ma25_prev is None:
        return {"symbol": symbol, "action": "SKIP", "reason": "指標算出不可", "price": latest_price}

    # ゴールデンクロス: MA5が前日MA25以下 → 今日MA25を上抜け
    golden_cross = ma5_prev <= ma25_prev and ma5_now > ma25_now
    # デッドクロス: MA5が前日MA25以上 → 今日MA25を下抜け
    dead_cross = ma5_prev >= ma25_prev and ma5_now < ma25_now

    result = {
        "symbol": symbol,
        "price": latest_price,
        "ma5": round(ma5_now, 1),
        "ma25": round(ma25_now, 1),
        "rsi": round(rsi_now, 1) if rsi_now else None,
    }

    if golden_cross:
        if rsi_now and rsi_now > 70:
            result["action"] = "SKIP"
            result["reason"] = "ゴールデンクロスだがRSI過熱(>70)"
        else:
            result["action"] = "BUY"
            result["reason"] = "ゴールデンクロス"
    elif dead_cross:
        if rsi_now and rsi_now < 30:
            result["action"] = "SKIP"
            result["reason"] = "デッドクロスだがRSI売られすぎ(<30)"
        else:
            result["action"] = "SELL"
            result["reason"] = "デッドクロス"
    else:
        result["action"] = "HOLD"
        result["reason"] = "シグナルなし"

    return result


def _calc_quantity(cash: float, price: float) -> int:
    """残高と価格から購入可能な数量を計算する。"""
    if price <= 0:
        return 0
    max_amount = cash * MAX_POSITION_RATIO
    qty = int(max_amount / price)
    return max(qty, 0)


def get_auto_trade_results() -> dict:
    """自動売買の結果を集計する。"""
    with get_db() as conn:
        # 全取引を銘柄別に集計
        trades = conn.execute(
            "SELECT symbol, market, side, quantity, price, executed_at "
            "FROM trades ORDER BY executed_at ASC"
        ).fetchall()

        holdings = conn.execute(
            "SELECT h.symbol, h.market, h.quantity, h.avg_cost, s.name "
            "FROM portfolio_holdings h "
            "LEFT JOIN stocks s ON h.symbol = s.symbol AND h.market = s.market"
        ).fetchall()

    # 銘柄ごとの損益を集計
    stock_results: dict[str, dict] = {}
    positions: dict[str, list[tuple[int, float]]] = {}

    for t in trades:
        symbol = t["symbol"]
        if symbol not in stock_results:
            stock_results[symbol] = {
                "symbol": symbol,
                "buy_count": 0,
                "sell_count": 0,
                "total_buy": 0.0,
                "total_sell": 0.0,
                "realized_pnl": 0.0,
                "trades": [],
            }

        r = stock_results[symbol]
        if t["side"] == "BUY":
            r["buy_count"] += 1
            r["total_buy"] += t["quantity"] * t["price"]
            positions.setdefault(symbol, []).append((t["quantity"], t["price"]))
        else:
            r["sell_count"] += 1
            r["total_sell"] += t["quantity"] * t["price"]
            # FIFO損益
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

    # 結果リスト
    results = list(stock_results.values())
    for r in results:
        r["win"] = r["realized_pnl"] > 0
        r["status"] = "利益" if r["realized_pnl"] > 0 else ("損失" if r["realized_pnl"] < 0 else "未確定")

    # 保有中の含み損益を追加
    for h in holdings:
        symbol = h["symbol"]
        if symbol not in stock_results:
            stock_results[symbol] = {
                "symbol": symbol,
                "buy_count": 0, "sell_count": 0,
                "total_buy": 0.0, "total_sell": 0.0,
                "realized_pnl": 0.0, "win": False, "status": "保有中",
            }

    # サマリー
    total_pnl = sum(r["realized_pnl"] for r in results)
    closed = [r for r in results if r["sell_count"] > 0]
    wins = [r for r in closed if r["realized_pnl"] > 0]
    losses = [r for r in closed if r["realized_pnl"] <= 0]

    return {
        "summary": {
            "total_stocks": len(results),
            "total_pnl": total_pnl,
            "win_count": len(wins),
            "lose_count": len(losses),
            "win_rate": len(wins) / len(closed) if closed else 0.0,
        },
        "results": sorted(results, key=lambda r: r["realized_pnl"], reverse=True),
    }
