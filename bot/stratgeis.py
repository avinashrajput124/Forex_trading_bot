
import MetaTrader5 as mt5

# ================= STRATEGIES =================

def ema_trend_strategy(symbol, timeframe, fast=10, slow=30):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, slow + 2)
    if rates is None or len(rates) < slow:
        return None

    closes = rates['close']
    ema_fast = sum(closes[-fast:]) / fast
    ema_slow = sum(closes[-slow:]) / slow

    if ema_fast > ema_slow:
        return "BUY"
    elif ema_fast < ema_slow:
        return "SELL"
    return None


def rsi_strategy(symbol, timeframe, period=14):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 2)
    if rates is None:
        return None

    closes = rates['close']
    gains, losses = [], []

    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains) / period if gains else 0.0001
    avg_loss = sum(losses) / period if losses else 0.0001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    if rsi < 30:
        return "BUY"
    elif rsi > 70:
        return "SELL"
    return None


def ema_rsi_strategy(symbol, timeframe):
    ema = ema_trend_strategy(symbol, timeframe)
    rsi = rsi_strategy(symbol, timeframe)

    if ema == "BUY" and rsi == "BUY":
        return "BUY"
    if ema == "SELL" and rsi == "SELL":
        return "SELL"
    return None


# ================= EMA REAL CROSS STRATEGY =================
def ema_cross_strategy(symbol, timeframe, fast=10, slow=30):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, slow + 3)
    if rates is None or len(rates) < slow + 2:
        return None

    closes = rates['close']

    ema_fast_prev = sum(closes[-fast-1:-1]) / fast
    ema_slow_prev = sum(closes[-slow-1:-1]) / slow

    ema_fast_now = sum(closes[-fast:]) / fast
    ema_slow_now = sum(closes[-slow:]) / slow

    if ema_fast_prev < ema_slow_prev and ema_fast_now > ema_slow_now:
        return "BUY"

    if ema_fast_prev > ema_slow_prev and ema_fast_now < ema_slow_now:
        return "SELL"

    return None