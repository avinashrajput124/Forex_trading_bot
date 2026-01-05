from django.urls import path,re_path
from .consumers import LivePriceConsumer,OpenTradesConsumer,AccountInfoConsumer

websocket_urlpatterns = [
    path("ws/live-price/", LivePriceConsumer.as_asgi()),
    path("ws/open-trades/", OpenTradesConsumer.as_asgi()),
    path("ws/account-info/", AccountInfoConsumer.as_asgi()),



]
