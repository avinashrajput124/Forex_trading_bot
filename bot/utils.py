from django.http import JsonResponse
from datetime import datetime,time
import MetaTrader5 as mt5
from .models import TradingBot
import pytz

def api_success(message="Success", data=None):
    return JsonResponse({
        "status": "success",
        "comment": message,
        "data": data or {}
    })


def api_error(message="Error", error=None):
    print(message,"message",error,"error")
    return JsonResponse({
        "status": "error",
        "comment": message,
        "error": str(error) if error else None
    })

UTC = pytz.utc

SESSION_TIME_MAP = {
    "asia":      (time(0, 0),  time(6, 0)),
    "london":    (time(8, 0),  time(11, 0)),
    "newyork":   (time(13, 0), time(20, 0)),
    "london_ny": (time(13, 0), time(16, 0)),
    "all":       (time(0, 0),  time(23, 59)),
}

def is_session_allowed(session: str, check_dt: datetime = None) -> bool:
    """
     Trade sirf session START → END ke beech allowed
    Session ke baad poora din no trade
     Next day same session time par hi allow
    """
    if session == "all":
        return True

    if session not in SESSION_TIME_MAP:
        return False

    now = check_dt or datetime.now(UTC)
    current_time = now.time()

    start_time, end_time = SESSION_TIME_MAP[session]

    return start_time <= current_time < end_time
