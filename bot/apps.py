from django.apps import AppConfig
from .mt5_connect import connect



# class BotConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'bot'

class BotConfig(AppConfig):
    name = 'bot'

    def ready(self):
        connect()
        from bot.trading_engine import start_master_engine
        start_master_engine()