from django.http import JsonResponse

import MetaTrader5 as mt5
 
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