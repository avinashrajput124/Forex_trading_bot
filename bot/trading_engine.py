import MetaTrader5 as mt5
import time
import threading
from .models import TradingBot
from .stratgeis import *
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
}



# ================= START MASTER ENGINE =================
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

# ================= MASTER ENGINE =================
def master_bot_engine():
    print("Master Trading Engine Started")

    if not mt5.initialize():
        print("MT5 INIT FAILED")
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
    print(f"Bot {bot_id} started")

    while True:
        bot = TradingBot.objects.get(id=bot_id)

        if not bot.is_running:
            print(f"Bot {bot_id} stopped")
            break

        try:
            with ENGINE_LOCK:  
                run_single_bot(bot)
        except Exception as e:
            print(f"[Bot {bot_id}] ERROR:", e)

        time.sleep(1)

# ================= SINGLE BOT EXECUTION =================
def run_single_bot(bot):
    symbol = bot.symbol
    lot = float(bot.lot)
    timeframe = TIMEFRAME_MAP.get(bot.timeframe, mt5.TIMEFRAME_M1)

    # ---------- SIGNAL ----------
    signal = None
    if bot.strategy == "ema_cross":
        signal = ema_trend_strategy(symbol, timeframe)

    print(f"[Bot {bot.id}] SIGNAL = {signal}")  # 👈 DEBUG

    if not signal:
        return

    positions = mt5.positions_get(symbol=symbol) or []
    my_positions = [p for p in positions if p.magic == bot.id]

    # ---------- TRAILING ----------
    if my_positions:
        manage_trailing(bot, my_positions)
        return

    # ---------- OPEN TRADE ----------
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)

    if not tick or not info:
        print("Tick / Symbol info missing")
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
    }

    result = mt5.order_send(request)

    print("ORDER RESULT:", result) 

    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"[Bot {bot.id}] {signal} EXECUTED @ {price}")
    else:
        print(f"ORDER FAILED | retcode={result.retcode if result else 'None'}")

# ================= PROFESSIONAL TRAILING STOP =================
def manage_trailing(bot, positions):
    tick = mt5.symbol_info_tick(bot.symbol)
    info = mt5.symbol_info(bot.symbol)

    if not tick or not info:
        return

    point = info.point
    digits = info.digits

    # ---------- SETTINGS ----------
    BREAKEVEN_R = 1.0      # 1R = SL to entry
    TRAIL_R = 1.5          # trail after 1.5R
    ATR_PERIOD = 14
    ATR_MULTIPLIER = 1.2   # breathing space

    atr = get_atr(bot.symbol, ATR_PERIOD)
    if not atr:
        return

    atr_buffer = atr * ATR_MULTIPLIER

    for p in positions:
        entry = p.price_open
        sl = p.sl
        tp = p.tp

        # ================= BUY =================
        if p.type == mt5.ORDER_TYPE_BUY:
            current_price = tick.bid

            risk = entry - sl
            if risk <= 0:
                continue

            profit = current_price - entry

            #  BREAKEVEN
            if profit >= BREAKEVEN_R * risk and sl < entry:
                mt5.order_send({
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": p.ticket,
                    "sl": round(entry, digits),
                    "tp": tp
                })
                continue

            # SMART TRAIL (STRUCTURE + ATR)
            if profit >= TRAIL_R * risk:
                new_sl = current_price - atr_buffer
                if new_sl > sl:
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": p.ticket,
                        "sl": round(new_sl, digits),
                        "tp": tp
                    })

        # ================= SELL =================
        elif p.type == mt5.ORDER_TYPE_SELL:
            current_price = tick.ask

            risk = sl - entry
            if risk <= 0:
                continue

            profit = entry - current_price

            # BREAKEVEN
            if profit >= BREAKEVEN_R * risk and sl > entry:
                mt5.order_send({
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": p.ticket,
                    "sl": round(entry, digits),
                    "tp": tp
                })
                continue

            # SMART TRAIL
            if profit >= TRAIL_R * risk:
                new_sl = current_price + atr_buffer
                if new_sl < sl:
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": p.ticket,
                        "sl": round(new_sl, digits),
                        "tp": tp
                    })


def get_atr(symbol, period=14, timeframe=mt5.TIMEFRAME_M5):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 2)
    if rates is None:
        return None

    trs = []
    for i in range(1, len(rates)):
        high = rates[i]['high']
        low = rates[i]['low']
        prev_close = rates[i-1]['close']
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        trs.append(tr)

    return sum(trs[-period:]) / period
