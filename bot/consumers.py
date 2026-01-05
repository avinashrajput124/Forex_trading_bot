import json
import time
import threading
from channels.generic.websocket import WebsocketConsumer,AsyncWebsocketConsumer
from datetime import datetime
import MetaTrader5 as mt5
from asgiref.sync import sync_to_async
import math
from .models import *


# class AccountInfoConsumer(WebsocketConsumer):

#     def connect(self):
#         self.accept()
#         self.running = True

#         # Background thread start
#         threading.Thread(target=self.send_account_info).start()

#     def disconnect(self, close_code):
#         self.running = False

#     def send_account_info(self):
#         while self.running:
#             acc = mt5.account_info()

#             if acc is None:
#                 data = {
#                     "balance": 0,
#                     "equity": 0,
#                     "free_margin": 0
#                 }
#             else:
#                 data = {
#                     "balance": round(acc.balance, 2),
#                     "equity": round(acc.equity, 2),
#                     "free_margin": round(acc.margin_free, 2)
#                 }

#             self.send(text_data=json.dumps(data))
#             time.sleep(2)  

class AccountInfoConsumer(WebsocketConsumer):

    def connect(self):
        self.accept()
        self.running = True
        self.login = self.scope["session"].get("mt5_login")

        threading.Thread(
            target=self.send_account_info,
            daemon=True
        ).start()

    def disconnect(self, close_code):
        self.running = False

    def send_account_info(self):
        while self.running:
            acc = mt5.account_info()

            bots = TradingBot.objects.filter(
                account__login=self.login,
                is_running=True
            ) if self.login else []
            print(bots,"bots")

            strategies = []
            for bot in bots:
                strategies.append({
                    "id": bot.id,
                    "account":bot.account.login,
                    "strategy": bot.get_strategy_display(),  # EMA Crossover
                    "strategy_code": bot.strategy,           # ema_cross
                    "symbol": bot.symbol,
                    "timeframe": bot.timeframe,
                    "lot": bot.lot,
                    "status": "Running" if bot.is_running else "Stopped",
                    "started_at": bot.created_at.strftime("%d %b %Y %H:%M")
                })

            data = {
                "balance": round(acc.balance, 2) if acc else 0,
                "equity": round(acc.equity, 2) if acc else 0,
                "free_margin": round(acc.margin_free, 2) if acc else 0,
                "bot_running": bots.exists() if self.login else False,
                "strategies": strategies,
                "account":self.login,

            }

            self.send(text_data=json.dumps(data))
            time.sleep(2)

class LivePriceConsumer(WebsocketConsumer):

    def connect(self):
        self.accept()
        self.running = True
        self.symbol = "EURUSD"   # default

        if not mt5.initialize():
            self.send(text_data=json.dumps({
                "error": "MT5 not connected"
            }))
            return

        self.thread = threading.Thread(target=self.stream_price)
        self.thread.start()

    def disconnect(self, close_code):
        self.running = False

    def receive(self, text_data):
        """
        Frontend se symbol aayega
        """
        data = json.loads(text_data)
        symbol = data.get("symbol")

        if symbol:
            self.symbol = symbol
            mt5.symbol_select(self.symbol, True)

    def stream_price(self):
        while self.running:
            tick = mt5.symbol_info_tick(self.symbol)

            if tick:
                self.send(text_data=json.dumps({
                    "symbol": self.symbol,
                    "bid": round(tick.bid, 2),
                    "ask": round(tick.ask, 2)
                }))

            time.sleep(1) 
class OpenTradesConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()
        self.running = True

        if not mt5.initialize():
            self.send(text_data=json.dumps({
                "error": "MT5 not connected"
            }))
            return

        self.thread = threading.Thread(
            target=self.stream_positions,
            daemon=True
        )
        self.thread.start()

    def disconnect(self, close_code):
        self.running = False

    def stream_positions(self):
        while self.running:
            positions = mt5.positions_get()
            data = []

            if positions:
                for p in positions:
                    deal_time = datetime.fromtimestamp(
                        p.time
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    # 🔥 FIX: strategy & timeframe via magic number
                    bot = TradingBot.objects.filter(id=p.magic).first()

                    strategy_name = (
                        bot.get_strategy_display()
                        if bot else "Manual"
                    )

                    timeframe = (
                        bot.timeframe
                        if bot else "-"
                    )

                    data.append({
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "lot": p.volume,
                        "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                        "price_open": round(p.price_open, 2),
                        "current_price": round(p.price_current, 2),
                        "profit": round(p.profit, 2),
                        "open_time": deal_time,
                        "sl": round(p.sl, 2),
                        "tp": round(p.tp, 2),
                        "strategy": strategy_name,
                        "timeframe": timeframe
                    })

            self.send(text_data=json.dumps({
                "positions": data
            }))

            time.sleep(1)
