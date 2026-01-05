from django.urls import path
from .views import *

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('login/',login_page, name='login_page'),
    path('validate-mt5/', validate_mt5, name='validate_mt5'),
    path('logout/', logout_view, name='logout'),
    # path("account/", account_info),
    path("symbols/", broker_symbols),
    path("manual_trade/", manual_trade),
    path("close_trade/", close_trade, name="close_trade"),
    path("start/", start_bot),
    path("stop/", stop_bot),
    path("trade_history/", trade_history),
]
