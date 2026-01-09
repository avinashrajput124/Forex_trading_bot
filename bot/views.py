from django.http import JsonResponse, HttpResponseRedirect
import MetaTrader5 as mt5
import threading, time, math, json
from django.shortcuts import render
from datetime import datetime, timedelta, timezone
from django.views.decorators.csrf import csrf_exempt
from .models import *
from .trading_engine import *
from .utils import *
from django.core.paginator import Paginator
from .backtest_engine import run_backtest
BOT_REGISTRY = {}


# ---------- AUTH ----------
def login_page(request):
    if request.session.get("mt5_logged_in"):
        return HttpResponseRedirect("/")
    return render(request, "login.html")


@csrf_exempt
def validate_mt5(request):
    if request.method != "POST":
        return api_error("Invalid request method")

    try:
        data = json.loads(request.body)
        login = int(data.get("login", 0))
        password = data.get("password")
        server = data.get("server")

        if not login or not password or not server:
            return api_error("All fields are required")

        if not mt5.initialize(login=login, password=password, server=server):
            return api_error("Invalid MT5 credentials")

        info = mt5.account_info()
        mt5.shutdown()

        if not info:
            return api_error("Unable to fetch account info")

        request.session["mt5_logged_in"] = True
        request.session["mt5_login"] = login
        request.session["mt5_server"] = server
        request.session["mt5_balance"] = float(info.balance)

        MT5Account.objects.update_or_create(
            login=login,
            defaults={"server": server, "is_active": True}
        )

        return api_success(
            f"Connected successfully. Balance {round(info.balance,2)} USD",
            {"balance": info.balance}
        )

    except Exception as e:
        return api_error("Login failed", str(e))


def logout_view(request):
    request.session.flush()
    return HttpResponseRedirect("/login")


def dashboard(request):
    if not request.session.get("mt5_logged_in"):
        return HttpResponseRedirect("/login")

    return render(request, "dashboard.html", {
        "login": request.session.get("mt5_login"),
        "server": request.session.get("mt5_server"),
        "balance": request.session.get("mt5_balance"),
    })


# ---------- MT5 HELPER ----------
def ensure_mt5(request):
    if mt5.initialize():
        return True

    acc = MT5Account.objects.filter(
        login=request.session.get("mt5_login"),
        is_active=True
    ).first()

    if not acc:
        return False

    return mt5.initialize(login=acc.login, server=acc.server)


# ---------- ACCOUNT INFO ----------
def account_info(request):
    if not ensure_mt5(request):
        return JsonResponse({
            "balance": 0,
            "equity": 0,
            "free_margin": 0,
            "bot_running": False,
            "strategies": []
        })

    acc = mt5.account_info()
    if not acc:
        return JsonResponse({
            "balance": 0,
            "equity": 0,
            "free_margin": 0,
            "bot_running": False,
            "strategies": []
        })

    login = request.session.get("mt5_login")

    bots = TradingBot.objects.filter(
        account__login=login,
        is_running=True
    )
    return JsonResponse({
        "balance": round(acc.balance, 2),
        "equity": round(acc.equity, 2),
        "free_margin": round(acc.margin_free, 2),
        "bot_running": bots.exists(),
        "strategies": [bot.strategy for bot in bots]
        # agar display name chahiye:
        # "strategies": [bot.get_strategy_display() for bot in bots]
    })


# ---------- SYMBOLS ----------
# ---------- SYMBOLS ----------
def broker_symbols(request):
    if not ensure_mt5(request):
        return api_error("MT5 not connected")

    allowed_symbols = {
        # ---- GOLD ----
        "XAUUSD",
        "XAUUSDm",
        "XAUUSD.",
        "GOLD",
        "GOLDm",

        # ---- FOREX ----
        "GBPUSD",
        "EURUSD",
        "USDJPY",
        "GBPJPY",

        # ---- CRYPTO ----
        "BTCUSD",
        "BTCUSDm",
        "BTCUSD.",
    }

    symbols = mt5.symbols_get()
    data = [s.name for s in symbols if s.name in allowed_symbols]

    return JsonResponse({"symbols": data})


@csrf_exempt
def run_backtest_api(request):
    if request.method != "POST":
        return api_error("Invalid request")
    data = json.loads(request.body)
    print("Backtest API Data:", data)

    result = run_backtest(
        symbol=data["symbol"],
        timeframe_key=data["timeframe"],
        strategy=data["strategy"],
        session=data.get("session", "all"),
        from_date=data["from_date"],
        to_date=data["to_date"],
        lot=float(data.get("lot", 0.01)),
         sl_pips=20,  # stop-loss in pips
    tp_pips=40 
    )
    print("Backtest Result:", result)

    return JsonResponse(result)

# ---------- MANUAL TRADE ----------
def manual_trade(request):
    try:
        # ------------------ MT5 CONNECTION ------------------
        if not ensure_mt5(request):
            return api_error("MT5 not connected")

        # ------------------ PARAMETERS ------------------
        symbol = request.GET.get("symbol")
        tf = request.GET.get("tf")
        side = request.GET.get("side")
        lot = request.GET.get("lot")

        if not all([symbol, tf, side, lot]):
            return api_error("Missing required parameters")

        # ------------------ LOT VALIDATION ------------------
        try:
            lot = float(lot)
            if lot <= 0:
                
                return api_error("Lot must be greater than 0")
        except ValueError:
            return api_error("Lot must be numeric")

        # ------------------ USER / ACCOUNT ------------------
        user = MT5Account.objects.filter(
            login=request.session.get("mt5_login")
        ).first()
        if not user:
            return api_error("Trading account not found")

        # ------------------ SYMBOL VALIDATION ------------------
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return api_error(f"Symbol '{symbol}' not found in MT5")
        if not symbol_info.visible:
            mt5.symbol_select(symbol, True)

        # ------------------ PRICE DATA ------------------
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return api_error("No price data available for this symbol")

        order_type = mt5.ORDER_TYPE_BUY if side.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

        # ------------------ MARGIN CHECK ------------------
        acc = mt5.account_info()
        if not acc:
            return api_error("Failed to fetch account info")
        
        # Calculate required margin
        required_margin = mt5.order_calc_margin(order_type, symbol, lot, price)
        if required_margin is None:
            return api_error("Failed to calculate required margin")
        
        if required_margin > acc.margin_free:
            return api_error(
                f"Insufficient free margin. Required: {round(required_margin, 2)}, "
                f"Available: {round(acc.margin_free, 2)}"
            )

        # ------------------ SEND ORDER ------------------
        request_data = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 999,
            "comment": "Manual Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC, 
            # "type_filling": get_filling_mode(symbol),
        }

        result = mt5.order_send(request_data)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return api_error(f"Trade failed: {result.comment}", result.retcode)

        # ------------------ RECORD TRADE ------------------
        bot = TradingBot.objects.create(
            strategy="manual",
            account=user,
            symbol=symbol,
            timeframe=tf,
            lot=lot,
            is_running=False,
        )

        Tradehistory.objects.create(
            bot=bot,
            ticket=result.order,
            symbol=symbol,
            order_type=side.upper(),
            lot=lot,
            open_price=price,
            close_price=price,
            strategy="manual"
        )

        return api_success(f"{side.upper()} order placed successfully")

    except Exception as e:
        return api_error("Manual trade failed", str(e))
def close_trade(request):
    if not ensure_mt5(request):
        return api_error("MT5 not connected")

    ticket = request.GET.get("ticket")
    if not ticket:
        return api_error("Ticket required")

    ticket = int(ticket)

    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return api_error("Position not found")

    pos = positions[0]

    symbol = pos.symbol
    volume = pos.volume
    order_type = pos.type

    # opposite order type for closing
    if order_type == mt5.ORDER_TYPE_BUY:
        close_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    else:
        close_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask

    request_mt5 = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 0,
        "comment": "Closed via dashboard",
        "type_time": mt5.ORDER_TIME_GTC,
         "type_filling": mt5.ORDER_FILLING_IOC, 
    }

    result = mt5.order_send(request_mt5)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return JsonResponse({
            "success": False,
            "error": result.comment,
            "retcode": result.retcode
        })

    # ---------------- UPDATE TRADE HISTORY ----------------
    try:
        trade = Tradehistory.objects.filter(ticket=ticket).last()
        if trade:
            trade.close_price = price
            trade.profit = getattr(result, "profit", 0) or 0  # MT5 result profit might be available
            trade.save()
    except Exception as e:
        print(f"[TradeHistory Error] Could not update trade {ticket}: {e}")

    return api_success(f"{symbol} order closed successfully")

# ---------- START BOT ----------
def start_bot(request):
    try:
        # ------------------ MT5 CONNECTION ------------------
        if not ensure_mt5(request):
            return api_error("MT5 not connected")

        # ------------------ BASIC PARAMS ------------------
        symbol = request.GET.get("symbol")
        tf = request.GET.get("tf")
        lot = request.GET.get("lot")
        strategy = request.GET.get("strategy")
        session = request.GET.get("session", "any")

        if not all([symbol, tf, lot, strategy]):
            return api_error("Missing required parameters")

        try:
            lot = float(lot)
            if lot <= 0:
                return api_error("Invalid lot size")
        except ValueError:
            return api_error("Lot must be numeric")

        # ------------------ USER / ACCOUNT ------------------
        user = MT5Account.objects.filter(
            login=request.session.get("mt5_login")
        ).first()
        if not user:
            return api_error("Trading account not found")

        # ------------------ DUPLICATE STRATEGY CHECK ------------------
        bot = TradingBot.objects.filter(
            account=user,
            symbol=symbol,
            timeframe=tf,
            strategy=strategy
        ).first()

        if bot and bot.is_running:
            return api_error("This strategy is already running")

        # ------------------ SYMBOL VALIDATION ------------------
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return api_error("Symbol not found in MT5")
        if not symbol_info.visible:
            mt5.symbol_select(symbol, True)

        # ------------------ LOT LIMIT VALIDATION ------------------
        if lot < symbol_info.volume_min:
            return api_error(f"Lot too small (min {symbol_info.volume_min})")
        if lot > symbol_info.volume_max:
            return api_error(f"Lot too large (max {symbol_info.volume_max})")

        # ------------------ ACCOUNT INFO ------------------
        acc = mt5.account_info()
        if not acc:
            return api_error("Failed to fetch account info")

        # ------------------ REAL MARGIN CALCULATION ------------------
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return api_error("Failed to fetch market price")
        price = tick.ask

        required_margin = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY,
            symbol,
            lot,
            price
        )
        if required_margin is None:
            return api_error("Margin calculation failed")
        if required_margin > acc.margin_free:
            return api_error(
                f"Insufficient margin. Required: {round(required_margin, 2)}, "
                f"Available: {round(acc.margin_free, 2)}"
            )

        # ------------------ CREATE OR REUSE BOT ------------------
        if not bot:
            bot = TradingBot.objects.create(
                account=user,
                symbol=symbol,
                timeframe=tf,
                lot=lot,
                strategy=strategy,
                session=session,
                is_running=True
            )
        else:
            bot.lot = lot
            bot.is_running = True
            bot.save()

        # ------------------ START THREAD ------------------
        
        # if bot.id not in BOT_REGISTRY or not BOT_REGISTRY[bot.id].is_alive():
        #     t = threading.Thread(
        #         target=bot_engine,
        #         args=(bot.id,),
        #         daemon=True
        #     )
        #     BOT_REGISTRY[bot.id] = t
        #     t.start()
        start_master_engine()

        return api_success(
            "Bot started successfully",
            {
                "bot_id": bot.id,
                "required_margin": round(required_margin, 2)
            }
        )

    except Exception as e:
        return api_error("Bot start failed", str(e))


# ---------- STOP BOT ----------

@csrf_exempt
def stop_bot(request):
    if request.method != "POST":
        return api_error("Invalid method")

    if not request.body:
        return api_error("Empty request body")

    data = json.loads(request.body.decode())
    bot_id = data.get("bot_id")
    login = request.session.get("mt5_login")

    if not bot_id:
        return api_error("bot_id is required")

    try:
        bot = TradingBot.objects.get(
            id=bot_id,
            account__login=login,
            is_running=True
        )
        bot.is_running = False
        bot.save()

        return api_success("Bot stopped successfully")

    except TradingBot.DoesNotExist:
        return api_error("Running bot not found")
    
    
# ---------- TRADE HISTORY ----------
def trade_history(request):
    if not ensure_mt5(request):
        return api_error("MT5 not connected")

    page = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 10))

    from_date = datetime.now() - timedelta(days=30)
    deals = mt5.history_deals_get(from_date, datetime.now()) or []
    deals = list(deals)[::-1]

    total_pages = math.ceil(len(deals) / per_page)
    start = (page - 1) * per_page
    end = start + per_page

    data = []
    for d in deals[start:end]:
        t = datetime.fromtimestamp(d.time).strftime("%Y-%m-%d %H:%M:%S")
        data.append({
            "ticket": d.ticket,
            "symbol": d.symbol,
            "lot": d.volume,
            "type": "BUY" if d.type == mt5.ORDER_TYPE_BUY else "SELL",
            "price_open": round(d.price, 5),
            "price_close": round(d.price, 5),
            "profit": round(d.profit, 2),
            "open_time": t,
            "close_time": t,
            "strategy": d.comment or "Manual"
        })

    return JsonResponse({
        "history": data,
        "current_page": page,
        "total_pages": total_pages
    })




# # ---------- TRADE HISTORY (from DB) ----------
# def trade_history(request):
#     user_login = request.session.get("mt5_login")
#     user = MT5Account.objects.filter(login=user_login).first()
#     if not user:
#         return api_error("Trading account not found")

#     page = int(request.GET.get("page", 1))
#     per_page = int(request.GET.get("per_page", 10))

#     trades = Tradehistory.objects.filter(bot__account=user).order_by("-created_at")
    
#     paginator = Paginator(trades, per_page)
#     current_page = paginator.get_page(page)

#     data = []
#     for t in current_page:
#         # calculate profit properly
#         price_close = t.close_price if t.close_price is not None else t.open_price
#         profit = 0
#         if t.order_type.upper() == "BUY":
#             profit = (price_close - t.open_price) * t.lot
#         elif t.order_type.upper() == "SELL":
#             profit = (t.open_price - price_close) * t.lot
        
#         data.append({
#             "ticket": t.ticket,
#             "symbol": t.symbol,
#             "lot": t.lot,
#             "type": t.order_type,
#             "price_open": t.open_price,
#             "price_close": price_close,
#             "profit": round(profit, 2),
#             "sl": getattr(t, "sl", None),
#             "tp": getattr(t, "tp", None),
#             "open_time": t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
#             "close_time": t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
#             "strategy": t.strategy
#         })

#     return JsonResponse({
#         "history": data,
#         "current_page": page,
#         "total_pages": paginator.num_pages
#     })



