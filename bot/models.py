from django.db import models
from django.contrib.auth.models import User

class MT5Account(models.Model):
    login = models.BigIntegerField()
    server = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.login}"


class TradingBot(models.Model):
    STRATEGIES = (
        ("ema_cross", "EMA Crossover"),
        ("ema_trend", "EMA Trend"),
        ("manual", "Manual"),
    )

    account = models.ForeignKey(MT5Account, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=20)
    timeframe = models.CharField(max_length=10)
    lot = models.FloatField()
    strategy = models.CharField(max_length=20, choices=STRATEGIES)
    is_running = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.account.login} | {self.strategy} | {self.symbol}"



class Tradehistory(models.Model):
    bot = models.ForeignKey(TradingBot, on_delete=models.CASCADE)
    ticket = models.BigIntegerField()
    symbol = models.CharField(max_length=20)
    order_type = models.CharField(max_length=10)
    lot = models.FloatField()
    open_price = models.FloatField()
    close_price = models.FloatField(null=True, blank=True)
    sl = models.FloatField(null=True, blank=True)   
    tp = models.FloatField(null=True, blank=True) 
    profit = models.FloatField(default=0)
    strategy = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.bot.account.login} - {self.strategy} - {self.symbol}"