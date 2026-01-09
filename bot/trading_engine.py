import MetaTrader5 as mt5
import time
import threading
from .models import TradingBot
from .stratgeis import *
from .utils import is_session_allowed

# ================= GLOBALS =================
ENGINE_RUNNING = False
ENGINE_THREAD = None
BOT_THREADS = {}
ENGINE_LOCK = threading.Lock()

# ================= TIMEFRAME MAP =================
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "D2": "D2",   # custom 2 Day
}

# ================= RATE FETCHER =================
def get_rates(symbol, timeframe, bars):
    if timeframe == "D2":
        return mt5.copy_rates_from_pos(
            symbol, mt5.TIMEFRAME_D1, 0, bars * 2
        )
    return mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)

# ================= MASTER ENGINE =================
def start_master_engine():
    global ENGINE_RUNNING, ENGINE_THREAD
    if ENGINE_RUNNING:
        return

    ENGINE_RUNNING = True
    ENGINE_THREAD = threading.Thread(
        target=master_bot_engine,
        daemon=True
    )
    ENGINE_THREAD.start()


def master_bot_engine():
    print("🚀 Master Trading Engine Started")

    if not mt5.initialize():
        print("❌ MT5 INIT FAILED")
        return

    while ENGINE_RUNNING:
        bots = TradingBot.objects.filter(is_running=True)
        for bot in bots:
            if bot.id not in BOT_THREADS or not BOT_THREADS[bot.id].is_alive():
                t = threading.Thread(
                    target=run_bot_loop,
                    args=(bot.id,),
                    daemon=True
                )
                BOT_THREADS[bot.id] = t
                t.start()
        time.sleep(2)

# ================= BOT LOOP =================
def run_bot_loop(bot_id):
    print(f"🤖 Bot {bot_id} started")

    while True:
        bot = TradingBot.objects.get(id=bot_id)
        if not bot.is_running:
            print(f" Bot {bot_id} stopped")
            break
        # SESSION FILTER
        if not is_session_allowed(bot.session):
            print(f"⏸ Bot {bot_id} waiting for {bot.session} session")
            time.sleep(30)
            continue

        try:
            with ENGINE_LOCK:
                run_single_bot(bot)
        except Exception as e:
            print(f"[Bot {bot_id}] ERROR:", e)

        time.sleep(1)

# ================= SINGLE BOT =================
def run_single_bot(bot):
    symbol = bot.symbol
    lot = float(bot.lot)

    tf_key = bot.timeframe
    timeframe = TIMEFRAME_MAP.get(tf_key, mt5.TIMEFRAME_M5)

    # ---------- SIGNAL ----------
    signal = None
    if bot.strategy == "adx_ema_mtf": #1
        signal = ema_mtf_adx_strategy(symbol, timeframe)
    elif bot.strategy == "ema_cross":#2
        signal = ema_cross_strategy(symbol, timeframe)
    elif bot.strategy == "ema_rsi":#3
        signal = ema_rsi_strategy(symbol, timeframe)   
    elif bot.strategy == "ema_trend":#4
        signal = ema_trend_strategy(symbol, timeframe)
 
  
  

    print(f"[Bot {bot.id}] TF={tf_key} SIGNAL={signal}")

    if not signal:
        return

    positions = mt5.positions_get(symbol=symbol) or []
    my_positions = [p for p in positions if p.magic == bot.id]

    if my_positions:
        manage_trailing(bot, my_positions)
        return

    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if not tick or not info:
        return

    price = tick.ask if signal == "BUY" else tick.bid
    point = info.point

    sl = price - 200 * point if signal == "BUY" else price + 200 * point
    tp = price + 400 * point if signal == "BUY" else price - 400 * point

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": round(price, info.digits),
        "sl": round(sl, info.digits),
        "tp": round(tp, info.digits),
        "deviation": 30,
        "magic": bot.id,
        "comment": bot.strategy,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    print("ORDER RESULT:", result)

# ================= ATR =================
def get_atr(symbol, timeframe, period=14):
    rates = get_rates(symbol, timeframe, period + 2)
    if rates is None or len(rates) < period + 2:
        return None

    trs = []
    for i in range(1, len(rates)):
        h = rates[i]['high']
        l = rates[i]['low']
        pc = rates[i - 1]['close']
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))

    return sum(trs[-period:]) / period

# ================= SWING =================
def last_swing_low(symbol, timeframe, lookback=5):
    rates = get_rates(symbol, timeframe, lookback + 1)
    if not rates:
        return None
    return min(r['low'] for r in rates[1:])


def last_swing_high(symbol, timeframe, lookback=5):
    rates = get_rates(symbol, timeframe, lookback + 1)
    if not rates:
        return None
    return max(r['high'] for r in rates[1:])

# ================= ORDER HELPERS =================
def modify_sl_tp(ticket, sl, tp):
    mt5.order_send({
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": sl,
        "tp": tp
    })


def close_partial(position, close_volume):
    symbol = position.symbol
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return

    close_type = (
        mt5.ORDER_TYPE_SELL
        if position.type == mt5.ORDER_TYPE_BUY
        else mt5.ORDER_TYPE_BUY
    )

    price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

    mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "position": position.ticket,
        "volume": round(close_volume, 2),
        "type": close_type,
        "price": price,
        "deviation": 20,
        "magic": 999,
        "type_filling": mt5.ORDER_FILLING_IOC,
    })

# ================= TRAILING =================
def manage_trailing(bot, positions):
    symbol = bot.symbol
    tf_key = bot.timeframe
    timeframe = TIMEFRAME_MAP.get(tf_key, mt5.TIMEFRAME_M5)

    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if not tick or not info:
        return

    atr = get_atr(symbol, timeframe)
    if not atr:
        return

    buffer = atr * 0.30
    digits = info.digits

    for p in positions:
        entry = p.price_open
        sl = p.sl
        tp = p.tp
        vol = p.volume

        # ===== BUY =====
        if p.type == mt5.ORDER_TYPE_BUY:
            price = tick.bid
            risk = entry - sl
            if risk <= 0:
                continue

            profit = price - entry

            if profit >= risk and vol > 0.02:
                close_partial(p, vol * 0.5)
                modify_sl_tp(p.ticket, round(entry + buffer, digits), tp)

            if profit >= 2 * risk:
                swing = last_swing_low(symbol, timeframe)
                if swing:
                    new_sl = round(swing - buffer, digits)
                    if new_sl > sl:
                        modify_sl_tp(p.ticket, new_sl, tp)

        # ===== SELL =====
        elif p.type == mt5.ORDER_TYPE_SELL:
            price = tick.ask
            risk = sl - entry
            if risk <= 0:
                continue

            profit = entry - price

            if profit >= risk and vol > 0.02:
                close_partial(p, vol * 0.5)
                modify_sl_tp(p.ticket, round(entry - buffer, digits), tp)

            if profit >= 2 * risk:
                swing = last_swing_high(symbol, timeframe)
                if swing:
                    new_sl = round(swing + buffer, digits)
                    if new_sl < sl:
                        modify_sl_tp(p.ticket, new_sl, tp)
