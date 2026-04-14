"""テクニカル指標の計算ロジック。Pure Python 実装。"""

from __future__ import annotations

import math
from datetime import date


def _validate_inputs(
    dates: list[date], closes: list[float], period: int | None = None
) -> bool:
    """入力データを検証する。不正な場合は False を返す。"""
    if len(dates) != len(closes):
        return False
    if len(dates) == 0:
        return True  # 空は許容（空結果を返す）
    if period is not None and period <= 0:
        return False
    # NaN/Inf チェック
    for c in closes:
        if math.isnan(c) or math.isinf(c):
            return False
    return True


def calc_ma(
    dates: list[date], closes: list[float], period: int
) -> list[tuple[date, float | None]]:
    """単純移動平均線（SMA）を計算する。"""
    if not _validate_inputs(dates, closes, period):
        return [(d, None) for d in dates] if len(dates) <= len(closes) else []

    result: list[tuple[date, float | None]] = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append((dates[i], None))
        else:
            avg = sum(closes[i - period + 1 : i + 1]) / period
            result.append((dates[i], avg))
    return result


def calc_rsi(
    dates: list[date], closes: list[float], period: int = 14
) -> list[tuple[date, float | None]]:
    """RSI（Wilder平滑化）を計算する。"""
    if not _validate_inputs(dates, closes, period):
        return [(d, None) for d in dates] if len(dates) <= len(closes) else []

    if len(closes) < period + 1:
        return [(d, None) for d in dates]

    # 日次変動
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    result: list[tuple[date, float | None]] = [(dates[0], None)]

    # 最初のperiod日間の平均上昇/下落
    gains = [max(d, 0) for d in deltas[:period]]
    losses = [max(-d, 0) for d in deltas[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for i in range(period):
        result.append((dates[i + 1], None))

    # 最初のRSI値
    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
    # period番目のdelta = deltas[period-1]、対応する日付 = dates[period]
    # resultにはdates[0]〜dates[period]まで入っている（period+1個）
    # 最後のNoneをRSI値に置き換え
    result[-1] = (dates[period], rsi)

    # Wilder平滑化で残りを計算
    for i in range(period, len(deltas)):
        delta = deltas[i]
        gain = max(delta, 0)
        loss = max(-delta, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        result.append((dates[i + 1], rsi))

    return result


def _ema(values: list[float], period: int) -> list[float | None]:
    """指数移動平均（EMA）を計算する。"""
    result: list[float | None] = []
    multiplier = 2.0 / (period + 1)
    ema_val: float | None = None

    for i, v in enumerate(values):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            ema_val = sum(values[: period]) / period
            result.append(ema_val)
        else:
            ema_val = (v - ema_val) * multiplier + ema_val
            result.append(ema_val)

    return result


def calc_macd(
    dates: list[date],
    closes: list[float],
    fast: int = 12,  # noqa: A002
    slow: int = 26,
    signal_period: int = 9,
) -> list[tuple[date, float | None, float | None, float | None]]:
    """MACD（MACD線、シグナル線、ヒストグラム）を計算する。"""
    if not _validate_inputs(dates, closes) or fast <= 0 or slow <= 0 or signal_period <= 0:
        return [(d, None, None, None) for d in dates] if len(dates) <= len(closes) else []

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    # MACD線 = EMA(fast) - EMA(slow)
    macd_line: list[float | None] = []
    for ef, es in zip(ema_fast, ema_slow):
        if ef is not None and es is not None:
            macd_line.append(ef - es)
        else:
            macd_line.append(None)

    # シグナル線 = MACD線のEMA(signal_period)
    # None以外の値だけでEMA計算し、元の位置に戻す
    valid_macd = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    signal_values = _ema([v for _, v in valid_macd], signal_period)

    signal_line: list[float | None] = [None] * len(closes)
    for (orig_idx, _), sig in zip(valid_macd, signal_values):
        signal_line[orig_idx] = sig

    # ヒストグラム = MACD線 - シグナル線
    result: list[tuple[date, float | None, float | None, float | None]] = []
    for i in range(len(dates)):
        m = macd_line[i]
        s = signal_line[i]
        h = (m - s) if (m is not None and s is not None) else None
        result.append((dates[i], m, s, h))

    return result


def calc_bollinger(
    dates: list[date],
    closes: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> list[tuple[date, float | None, float | None, float | None]]:
    """ボリンジャーバンド（上限、中央、下限）を計算する。"""
    if not _validate_inputs(dates, closes, period):
        return [(d, None, None, None) for d in dates] if len(dates) <= len(closes) else []

    result: list[tuple[date, float | None, float | None, float | None]] = []

    for i in range(len(closes)):
        if i < period - 1:
            result.append((dates[i], None, None, None))
        else:
            window = closes[i - period + 1 : i + 1]
            middle = sum(window) / period
            variance = sum((x - middle) ** 2 for x in window) / period
            std = math.sqrt(variance)
            upper = middle + num_std * std
            lower = middle - num_std * std
            result.append((dates[i], upper, middle, lower))

    return result
