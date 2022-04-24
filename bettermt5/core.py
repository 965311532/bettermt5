from typing import Union
import functools
import time

from MetaTrader5 import *
import MetaTrader5 as _mt5


from bettermt5.errors import MT5Error


def load_symbol(fn):
    @functools.wraps(fn)
    def wrapper(data: Union[str, dict], *args, **kwargs):
        symbol = data["symbol"] if isinstance(data, dict) else data
        loaded = _mt5.symbol_select(symbol)
        if not loaded:
            raise MT5Error(f"Couldn't load {symbol}")
        result = fn(data, *args, **kwargs)
        # Tries to deselect it, if it can't it's fine
        _mt5.symbol_select(symbol, False)
        return result

    return wrapper

@load_symbol
def symbol_info(symbol, *args, **kwargs):
    """Get data on the specified financial instrument."""
    for _ in range(10):
        info = _mt5.symbol_info(symbol, *args, **kwargs)
        if info.trade_tick_value > 0: # HACK: this is because of a bug in MT5 where sometimes it returns 0
            return info
        time.sleep(0.1)


@load_symbol
def symbol_info_tick(symbol, *args, **kwargs):
    """Get the last tick for the specified financial instrument."""
    for _ in range(10):
        tick = _mt5.symbol_info_tick(symbol, *args, **kwargs)
        if tick.time > 1:
            break
        time.sleep(0.1)
    if tick.time < 1:
        raise MT5Error(f"Couldn't load data for symbol {symbol}")
    return tick

@load_symbol
def order_send(order: dict, retries=10):
    """Send an order to the MetaTrader 5 terminal."""
    for _ in range(retries):
        r = _mt5.order_send(order)
        if r is None:
            return None
        if r.retcode != _mt5.TRADE_RETCODE_REQUOTE and r.retcode != _mt5.TRADE_RETCODE_PRICE_OFF:
            break
        time.sleep(0.1)
    return r