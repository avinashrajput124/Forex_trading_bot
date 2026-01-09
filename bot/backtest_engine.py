import MetaTrader5 as mt5
from datetime import datetime
import pytz
from .utils import UTC, is_session_allowed
from .stratgeis import *

# ================= TIMEFRAME MAP =================
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

MAX_BARS = 8000   # safety limit

# ================= INIT =================
def init_mt5():
    if not mt5.initialize():
        raise Exception("MT5 init failed")

# ================= DATA =================
def get_rates(symbol, timeframe, start, end):
    rates = mt5.copy_rates_range(symbol, timeframe, start, end)
    if rates is None or len(rates) == 0:
        raise Exception("No candles available")

    # safety trim
    if len(rates) > MAX_BARS:
        rates = rates[-MAX_BARS:]

    return rates

# ================= BACKTEST =================
def run_backtest(
    symbol,
    timeframe_key,
    strategy,
    session,
    from_date,
    to_date,
    lot=0.01,
    sl_pips=20,
    tp_pips=40
):
    init_mt5()

    tf = TIMEFRAME_MAP.get(timeframe_key)
    if not tf:
        return {"error": "Invalid timeframe"}

    start = datetime.strptime(from_date, "%Y-%m-%d")
    end   = datetime.strptime(to_date, "%Y-%m-%d")

    rates = get_rates(symbol, tf, start, end)
    print(f"Backtesting {symbol} {timeframe_key} | Session: {session}")

    balance = 10000.0
    trades = []
    position = None
    pip_value = 0.0001

    for i in range(50, len(rates)):
        candle = rates[i]
        price = candle['close']

        candle_time = datetime.fromtimestamp(
            candle['time'],
            tz=UTC
        )

        if not is_session_allowed(session, candle_time):
            continue

        # ===== SIGNAL =====
        signal = None
        try:
            if strategy == "adx_ema_mtf":
                signal = ema_mtf_adx_strategy(symbol, tf)
            elif strategy == "ema_cross":
                signal = ema_cross_strategy(symbol, tf)
            elif strategy == "ema_rsi":
                signal = ema_rsi_strategy(symbol, tf)
            elif strategy == "ema_trend":
                signal = ema_trend_strategy(symbol, tf)
        except:
            signal = None

        # ===== ENTRY =====
        if not position and signal:
            sl = price - sl_pips * pip_value if signal == "BUY" else price + sl_pips * pip_value
            tp = price + tp_pips * pip_value if signal == "BUY" else price - tp_pips * pip_value

            position = {
                "type": signal,
                "entry": price,
                "sl": sl,
                "tp": tp,
                "lot": lot
            }
            continue

        if not position:
            continue

        # ===== EXIT =====
        if position["type"] == "BUY":
            if price <= position["sl"] or price >= position["tp"]:
                pnl = (price - position["entry"]) * 100 * lot
                balance += pnl
                trades.append(pnl)
                position = None
        else:
            if price >= position["sl"] or price <= position["tp"]:
                pnl = (position["entry"] - price) * 100 * lot
                balance += pnl
                trades.append(pnl)
                position = None

    mt5.shutdown()

    wins = len([t for t in trades if t > 0])

    return {
        "symbol": symbol,
        "timeframe": timeframe_key,
        "strategy": strategy,
        "session": session,
        "total_trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "winrate": round((wins / len(trades)) * 100, 2) if trades else 0,
        "final_balance": round(balance, 2),
        "net_pnl": round(balance - 10000, 2)
    }
