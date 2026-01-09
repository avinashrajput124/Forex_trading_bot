import MetaTrader5 as mt5

# ================= STRATEGIES =================
# EMA_TREND:
# - Same timeframe par 2 EMAs compare karta hai (default 9 & 21)
# - Fast EMA > Slow EMA → BUY
# - Fast EMA < Slow EMA → SELL
# - Simple trend-following strategy
# - Sideways market me false signals aa sakte hain

def ema_trend_strategy(symbol, timeframe, fast=9, slow=21):
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

# EMA_RSI_CONFIRM:
# - EMA trend + RSI confirmation use karta hai
# - EMA direction batata hai trend
# - RSI oversold (<30) → BUY confirm
# - RSI overbought (>70) → SELL confirm
# - False signals kam karta hai

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

# EMA_CROSSOVER:
# - Real EMA crossover detect karta hai (previous + current candle)
# - 9 EMA crosses above 21 EMA → BUY
# - 9 EMA crosses below 21 EMA → SELL
# - Repainting nahi hota

# ================= EMA REAL CROSS STRATEGY =================
def ema_cross_strategy(symbol, timeframe, fast=9, slow=21):
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

# EMA_MTF_ADX:
# - Higher TF (1H) par 200 EMA se overall trend confirm karta hai
# - Lower TF (15M) par 9/21 EMA crossover se entry leta hai
# - ADX (>=25) se trend ki strength confirm karta hai
# - Sideways market completely avoid karta hai
# - BUY aur SELL dono support karta hai

# ==========================================================
# ============ EMA MTF + ADX (BUY / SELL) ==================
# ==========================================================

def get_adx(symbol, timeframe, period=14):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 20)
    if rates is None or len(rates) < period + 2:
        return None

    h = rates['high']
    l = rates['low']
    c = rates['close']

    tr, plus_dm, minus_dm = [], [], []

    for i in range(1, len(rates)):
        tr.append(max(
            h[i] - l[i],
            abs(h[i] - c[i - 1]),
            abs(l[i] - c[i - 1])
        ))

        up = h[i] - h[i - 1]
        down = l[i - 1] - l[i]

        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)

    atr = sum(tr[-period:]) / period
    if atr == 0:
        return None

    plus_di = 100 * (sum(plus_dm[-period:]) / period) / atr
    minus_di = 100 * (sum(minus_dm[-period:]) / period) / atr

    adx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    return adx


def ema_mtf_adx_strategy(symbol, timeframe):
    # ===== 1H TREND (200 EMA) =====
    h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 210)
    if h1 is None or len(h1) < 200:
        return None

    h1_close = h1['close']
    ema200 = sum(h1_close[-200:]) / 200
    price_h1 = h1_close[-1]

    # ===== 15M ENTRY (9/21 CROSS) =====
    m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 25)
    if m15 is None or len(m15) < 21:
        return None

    close15 = m15['close']

    ema9_prev = sum(close15[-10:-1]) / 9
    ema21_prev = sum(close15[-22:-1]) / 21

    ema9_now = sum(close15[-9:]) / 9
    ema21_now = sum(close15[-21:]) / 21

    # ===== ADX FILTER =====
    adx = get_adx(symbol, mt5.TIMEFRAME_M15)
    if not adx or adx < 25:
        return None

    # ===== BUY =====
    if price_h1 > ema200 and ema9_prev <= ema21_prev and ema9_now > ema21_now:
        return "BUY"

    # ===== SELL =====
    if price_h1 < ema200 and ema9_prev >= ema21_prev and ema9_now < ema21_now:
        return "SELL"

    return None
