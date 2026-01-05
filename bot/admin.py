from django.contrib import admin
from .models import MT5Account, TradingBot, Tradehistory

admin.site.register(MT5Account)
admin.site.register(TradingBot)
admin.site.register(Tradehistory)
