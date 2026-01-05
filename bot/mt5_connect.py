import MetaTrader5 as mt5

def connect():
    if not mt5.initialize():
        return False
    return True
