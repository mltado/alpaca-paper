import os
import sys
import asyncio
import inspect
import csv
from typing import Optional

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
try:
    # Optional: present in most versions; used for limit orders
    from alpaca.trading.requests import LimitOrderRequest  # type: ignore
except Exception:  # pragma: no cover
    LimitOrderRequest = None  # type: ignore
try:
    # Optional: for stop and stop-limit orders
    from alpaca.trading.requests import StopOrderRequest, StopLimitOrderRequest  # type: ignore
except Exception:  # pragma: no cover
    StopOrderRequest = None  # type: ignore
    StopLimitOrderRequest = None  # type: ignore
try:
    # Optional: for bracket orders
    from alpaca.trading.requests import TakeProfitRequest, StopLossRequest  # type: ignore
except Exception:  # pragma: no cover
    TakeProfitRequest = None  # type: ignore
    StopLossRequest = None  # type: ignore
from alpaca.trading.enums import OrderSide, TimeInForce
try:
    from alpaca.trading.enums import OrderClass  # type: ignore
except Exception:  # pragma: no cover
    OrderClass = None  # type: ignore

# Alpaca market data (historical + live) — optional imports
try:  # historical bars
    from alpaca.data.historical import StockHistoricalDataClient  # type: ignore
    from alpaca.data.requests import StockBarsRequest  # type: ignore
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit  # type: ignore
except Exception:  # pragma: no cover
    StockHistoricalDataClient = None  # type: ignore
    StockBarsRequest = None  # type: ignore
    try:
        from alpaca.data.timeframe import TimeFrame  # type: ignore
        TimeFrameUnit = None  # type: ignore
    except Exception:
        TimeFrame = None  # type: ignore
        TimeFrameUnit = None  # type: ignore

try:  # live streaming
    from alpaca.data.live import StockDataStream  # type: ignore
    try:
        from alpaca.data.enums import DataFeed  # type: ignore
    except Exception:  # pragma: no cover
        DataFeed = None  # type: ignore
except Exception:  # pragma: no cover
    StockDataStream = None  # type: ignore
    DataFeed = None  # type: ignore


def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_client() -> TradingClient:
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=False)
    load_dotenv(override=False)  # also load from workspace root if present

    key_id = os.getenv("ALPACA_API_KEY_ID")
    secret_key = os.getenv("ALPACA_API_SECRET_KEY")
    use_paper = env_bool("ALPACA_USE_PAPER", True)

    if not key_id or not secret_key:
        raise RuntimeError(
            "Missing ALPACA_API_KEY_ID/ALPACA_API_SECRET_KEY. Create an .env from .env.example."
        )

    return TradingClient(api_key=key_id, secret_key=secret_key, paper=use_paper)


def show_account_summary(client: TradingClient) -> None:
    account = client.get_account()
    print("Account ID:", account.id)
    print("Status:", account.status)
    print("Cash:", account.cash)
    print("Buying Power:", account.buying_power)
    print("Portfolio Value:", account.portfolio_value)


def list_positions(client: TradingClient) -> None:
    positions = client.get_all_positions()
    if not positions:
        print("No open positions.")
        return

    cols = [
        ("SYMBOL", 8),
        ("QTY", 8),
        ("MARKET_VAL", 14),
        ("UNRL_P/L", 12),
        ("UNRL_%", 8),
        ("AVG_ENTRY", 12),
        ("PRICE", 10),
    ]
    header = " ".join(name.ljust(w) for name, w in cols)
    print(header)
    print("-" * len(header))

    for p in positions:
        row = [
            str(getattr(p, "symbol", "")).ljust(8),
            str(getattr(p, "qty", "")).ljust(8),
            str(getattr(p, "market_value", "")).ljust(14),
            str(getattr(p, "unrealized_pl", "")).ljust(12),
            str(getattr(p, "unrealized_plpc", "")).ljust(8),
            str(getattr(p, "avg_entry_price", "")).ljust(12),
            str(getattr(p, "current_price", "")).ljust(10),
        ]
        print(" ".join(row))


def list_orders(client: TradingClient, limit: Optional[int] = None, status: Optional[str] = None, side: Optional[str] = None) -> None:
    # Build request with filters if supported by installed SDK; otherwise fall back.
    orders = None
    try:
        from alpaca.trading.requests import GetOrdersRequest  # type: ignore
        try:
            from alpaca.trading.enums import QueryOrderStatus as QStatus  # type: ignore
        except Exception:
            QStatus = None  # type: ignore

        req_kwargs = {}
        if limit is not None:
            req_kwargs["limit"] = int(limit)
        if status:
            st = status.strip().lower()
            if QStatus is not None:
                mapping = {"open": "OPEN", "closed": "CLOSED", "all": "ALL"}
                if st in mapping and hasattr(QStatus, mapping[st]):
                    req_kwargs["status"] = getattr(QStatus, mapping[st])
                else:
                    # Best-effort: some versions accept strings
                    req_kwargs["status"] = st
            else:
                req_kwargs["status"] = st

        orders = client.get_orders(GetOrdersRequest(**req_kwargs))
    except TypeError:
        # Older signature differences; retry without args
        orders = client.get_orders()
    except Exception:
        # As a last resort, try completely unfiltered
        try:
            orders = client.get_orders()
        except Exception as exc:
            raise RuntimeError(f"Unable to fetch orders: {exc}") from exc

    if not orders:
        print("No recent orders.")
        return

    # Local side filter if requested
    if side:
        s = side.strip().lower()
        orders = [o for o in orders if str(getattr(o, "side", "")).lower() == s]

    # Local limit if backend didn't apply it
    if limit is not None and len(orders) > limit:
        orders = orders[:limit]

    cols = [
        ("ID", 19),
        ("SYMBOL", 8),
        ("SIDE", 5),
        ("QTY", 6),
        ("STATUS", 10),
        ("SUBMITTED", 20),
        ("FILLED_QTY", 10),
    ]
    header = " ".join(name.ljust(w) for name, w in cols)
    print(header)
    print("-" * len(header))

    for o in orders:
        row = [
            str(getattr(o, "id", ""))[:19].ljust(19),
            str(getattr(o, "symbol", "")).ljust(8),
            str(getattr(o, "side", "")).ljust(5),
            str(getattr(o, "qty", getattr(o, "notional", ""))).ljust(6),
            str(getattr(o, "status", "")).ljust(10),
            str(getattr(o, "submitted_at", "")).ljust(20),
            str(getattr(o, "filled_qty", "")).ljust(10),
        ]
        print(" ".join(row))


def cancel_order_id(client: TradingClient, order_id: str) -> None:
    try:
        res = getattr(client, "cancel_order_by_id", None)
        if callable(res):
            res(order_id)
        else:
            client.cancel_order(order_id)  # type: ignore[attr-defined]
        print("Cancel requested for order:", order_id)
    except Exception as exc:
        print(f"Cancel failed for {order_id}: {exc}")


def cancel_all_orders(client: TradingClient) -> None:
    try:
        fn = getattr(client, "cancel_orders", None)
        if callable(fn):
            fn()
            print("Cancel requested for all open orders.")
            return
    except Exception as exc:
        print(f"Bulk cancel method not available: {exc}. Falling back to per-order.")

    # Fallback: enumerate open orders and cancel individually
    try:
        from alpaca.trading.requests import GetOrdersRequest  # type: ignore
        try:
            from alpaca.trading.enums import QueryOrderStatus as QStatus  # type: ignore
            orders = client.get_orders(GetOrdersRequest(status=QStatus.OPEN))
        except Exception:
            orders = client.get_orders(GetOrdersRequest())
    except Exception:
        try:
            orders = client.get_orders()
        except Exception as exc:
            print(f"Unable to enumerate open orders: {exc}")
            return

    if not orders:
        print("No open orders to cancel.")
        return

    for o in orders:
        oid = str(getattr(o, "id", ""))
        if not oid:
            continue
        cancel_order_id(client, oid)


def close_all_positions(client: TradingClient) -> None:
    try:
        fn = getattr(client, "close_all_positions", None)
        if callable(fn):
            fn()
            print("Close requested for all positions.")
            return
    except Exception as exc:
        print(f"Bulk close method not available: {exc}. Falling back to per-position.")

    try:
        positions = client.get_all_positions()
    except Exception as exc:
        print(f"Unable to enumerate positions: {exc}")
        return

    if not positions:
        print("No open positions to close.")
        return

    for p in positions:
        sym = getattr(p, "symbol", None)
        if sym:
            close_position_symbol(client, sym)


def show_order_status(client: TradingClient, order_id: str) -> None:
    order = None
    # Try multiple method names depending on SDK version
    for name in ("get_order_by_id", "get_order"):
        try:
            fn = getattr(client, name, None)
            if callable(fn):
                order = fn(order_id)
                break
        except Exception:
            continue
    if order is None:
        print(f"Unable to fetch order {order_id}.")
        return

    fields = [
        ("ID", getattr(order, "id", "")),
        ("SYMBOL", getattr(order, "symbol", "")),
        ("SIDE", getattr(order, "side", "")),
        ("TYPE", getattr(order, "type", "")),
        ("STATUS", getattr(order, "status", "")),
        ("QTY", getattr(order, "qty", getattr(order, "notional", ""))),
        ("FILLED_QTY", getattr(order, "filled_qty", "")),
        ("FILLED_AVG_PRICE", getattr(order, "filled_avg_price", "")),
        ("SUBMITTED_AT", getattr(order, "submitted_at", "")),
        ("UPDATED_AT", getattr(order, "updated_at", "")),
    ]
    for k, v in fields:
        print(f"{k}: {v}")


def close_position_symbol(client: TradingClient, symbol: str) -> None:
    sym = symbol.upper()
    # Try native close method(s)
    for name in ("close_position", "close_position_by_symbol"):
        fn = getattr(client, name, None)
        if callable(fn):
            try:
                res = fn(sym)  # type: ignore[misc]
                # Try to print resulting order(s)
                order_id = getattr(res, "id", None)
                if order_id:
                    print("Close requested for", sym, "order:", order_id)
                else:
                    try:
                        for r in res or []:  # type: ignore[operator]
                            print("Close requested for", sym, "order:", getattr(r, "id", ""))
                    except Exception:
                        print("Close requested for", sym)
                return
            except Exception as exc:
                print(f"Close via {name} failed for {sym}: {exc}")
                break

    # Fallback: manually flatten by submitting opposing market order
    try:
        p = client.get_open_position(sym)
    except Exception:
        print(f"No open position for {sym}.")
        return

    try:
        qty_i = int(getattr(p, "qty", 0))
    except Exception:
        print(f"Unable to determine quantity for {sym}.")
        return

    if qty_i == 0:
        print(f"Position for {sym} is already flat.")
        return

    side = OrderSide.SELL if qty_i > 0 else OrderSide.BUY
    order = MarketOrderRequest(
        symbol=sym,
        qty=abs(qty_i),
        side=side,
        time_in_force=TimeInForce.DAY,
    )
    submitted = client.submit_order(order)
    print("Submitted flatten order:", submitted.id, submitted.symbol, submitted.qty, submitted.side)


def show_position(client: TradingClient, symbol: str) -> None:
    try:
        p = client.get_open_position(symbol.upper())
    except Exception:
        print(f"No open position for {symbol.upper()}.")
        return

    print(f"SYMBOL: {getattr(p, 'symbol', '')}")
    print(f"QTY: {getattr(p, 'qty', '')}")
    print(f"MARKET VALUE: {getattr(p, 'market_value', '')}")
    print(f"UNREALIZED P/L: {getattr(p, 'unrealized_pl', '')}  ({getattr(p, 'unrealized_plpc', '')})")
    print(f"AVG ENTRY: {getattr(p, 'avg_entry_price', '')}")
    print(f"CURRENT PRICE: {getattr(p, 'current_price', '')}")


def _get_keys_for_data() -> tuple[str, str]:
    key_id = os.getenv("ALPACA_API_KEY_ID")
    secret_key = os.getenv("ALPACA_API_SECRET_KEY")
    if not key_id or not secret_key:
        raise RuntimeError("Missing ALPACA_API_KEY_ID/ALPACA_API_SECRET_KEY for market data.")
    return key_id, secret_key


def _parse_timeframe(s: Optional[str]):
    if TimeFrame is None:
        raise RuntimeError("TimeFrame not available in current alpaca-py version")
    if not s:
        return TimeFrame.Day
    t = s.replace(" ", "").lower()
    # Common aliases
    if t in ("1d", "1day", "day", "daily"): return TimeFrame.Day
    if t in ("1m", "1min", "minute"): return TimeFrame.Minute
    if t in ("5m", "5min"): 
        if TimeFrameUnit is not None:
            return TimeFrame(5, TimeFrameUnit.Minute)
        return TimeFrame.Minute
    if t in ("15m", "15min"):
        if TimeFrameUnit is not None:
            return TimeFrame(15, TimeFrameUnit.Minute)
        return TimeFrame.Minute
    if t in ("1h", "1hour", "hour"):
        if TimeFrameUnit is not None:
            return TimeFrame(1, TimeFrameUnit.Hour)
        # some versions have TimeFrame.Hour constant
        try:
            return TimeFrame.Hour  # type: ignore[attr-defined]
        except Exception:
            return TimeFrame.Day
    # Fallback
    return TimeFrame.Day


def show_history_bars(symbol: str, limit: int = 30, timeframe: Optional[str] = None) -> None:
    if StockHistoricalDataClient is None or StockBarsRequest is None or TimeFrame is None:
        raise RuntimeError("Historical bars not supported by current alpaca-py version")
    key, secret = _get_keys_for_data()
    client = StockHistoricalDataClient(key, secret)
    tf = _parse_timeframe(timeframe)
    req = StockBarsRequest(symbol_or_symbols=symbol.upper(), timeframe=tf, limit=int(limit))
    resp = client.get_stock_bars(req)
    bars = []
    # resp is usually a dict-like with symbol key
    try:
        bars = list(resp[symbol.upper()])  # type: ignore[index]
    except Exception:
        try:
            bars = list(resp.data)  # type: ignore[attr-defined]
        except Exception:
            pass
    if not bars:
        print("No bars returned.")
        return
    print("TS                O        H        L        C        V")
    for b in bars:
        ts = getattr(b, "timestamp", getattr(b, "time", ""))
        o = getattr(b, "open", "")
        h = getattr(b, "high", "")
        l = getattr(b, "low", "")
        c = getattr(b, "close", "")
        v = getattr(b, "volume", "")
        print(f"{ts} {str(o).rjust(7)} {str(h).rjust(7)} {str(l).rjust(7)} {str(c).rjust(7)} {str(v).rjust(8)}")


async def _watch_async(symbol: str, events: str = "trade", seconds: int = 30, feed: str = "iex", out_path: Optional[str] = None, append: bool = False) -> None:
    if StockDataStream is None:
        raise RuntimeError("Live streaming not supported by current alpaca-py version")
    key, secret = _get_keys_for_data()
    # Map string feed to enum if available
    feed_param = feed
    try:
        f = (feed or "iex").strip().lower()
    except Exception:
        f = "iex"
    if DataFeed is not None:
        if f == "sip" and hasattr(DataFeed, "SIP"):
            feed_param = DataFeed.SIP  # type: ignore[assignment]
        else:
            # default to IEX
            feed_param = getattr(DataFeed, "IEX", feed)
    stream = StockDataStream(key, secret, feed=feed_param)

    sym = symbol.upper()

    async def on_trade(t):
        print("TRADE", getattr(t, "symbol", sym), getattr(t, "price", ""), getattr(t, "size", getattr(t, "volume", "")), getattr(t, "timestamp", getattr(t, "t", "")))
        if writer:
            writer.writerow([
                _ts(t),
                "trade",
                getattr(t, "symbol", sym),
                getattr(t, "price", ""),
                getattr(t, "size", getattr(t, "volume", "")),
            ])

    async def on_quote(q):
        print("QUOTE", getattr(q, "symbol", sym), getattr(q, "bid_price", ""), getattr(q, "ask_price", ""), getattr(q, "timestamp", getattr(q, "t", "")))
        if writer:
            writer.writerow([
                _ts(q),
                "quote",
                getattr(q, "symbol", sym),
                getattr(q, "bid_price", ""),
                getattr(q, "ask_price", ""),
                getattr(q, "bid_size", ""),
                getattr(q, "ask_size", ""),
            ])

    async def on_bar(b):
        print("BAR", getattr(b, "symbol", sym), getattr(b, "open", ""), getattr(b, "high", ""), getattr(b, "low", ""), getattr(b, "close", ""), getattr(b, "volume", ""), getattr(b, "timestamp", getattr(b, "t", "")))
        if writer:
            writer.writerow([
                _ts(b),
                "bar",
                getattr(b, "symbol", sym),
                getattr(b, "open", ""),
                getattr(b, "high", ""),
                getattr(b, "low", ""),
                getattr(b, "close", ""),
                getattr(b, "volume", ""),
            ])

    # Subscribe with version-tolerant signatures
    def _subscribe(kind: str, cb, symbol_arg: str):
        try:
            if kind == "trades":
                stream.subscribe_trades(cb, symbol_arg)
            elif kind == "quotes":
                stream.subscribe_quotes(cb, symbol_arg)
            else:
                stream.subscribe_bars(cb, symbol_arg)
        except TypeError:
            # Some versions require a list of symbols
            arg = [symbol_arg]
            if kind == "trades":
                stream.subscribe_trades(cb, arg)
            elif kind == "quotes":
                stream.subscribe_quotes(cb, arg)
            else:
                stream.subscribe_bars(cb, arg)

    ev = events.strip().lower()
    # Setup CSV logging if requested
    writer = None
    fhandle = None
    if out_path:
        mode = "a" if append else "w"
        fhandle = open(out_path, mode, newline="", encoding="utf-8")
        writer = csv.writer(fhandle)

    def _ts(x):
        ts = getattr(x, "timestamp", getattr(x, "t", ""))
        try:
            return ts.isoformat()
        except Exception:
            return str(ts)

    # Write header per event type if not appending
    if writer and not append:
        if ev in ("trade", "trades"):
            writer.writerow(["ts", "event", "symbol", "price", "size"])  # trade header
        elif ev in ("quote", "quotes"):
            writer.writerow(["ts", "event", "symbol", "bid_price", "ask_price", "bid_size", "ask_size"])  # quote header
        else:
            writer.writerow(["ts", "event", "symbol", "open", "high", "low", "close", "volume"])  # bar header
            
    if ev in ("trade", "trades"):
        _subscribe("trades", on_trade, sym)
    elif ev in ("quote", "quotes"):
        _subscribe("quotes", on_quote, sym)
    else:
        _subscribe("bars", on_bar, sym)
    print(f"Subscribed to {ev} for {sym} on feed {feed_param if 'feed_param' in locals() else feed}.")

    # Determine runner and start as a background task
    runner = None
    runner_name = None
    for name in ("run", "consume", "start"):
        m = getattr(stream, name, None)
        if callable(m):
            runner = m
            runner_name = name
            break
    if runner is None:
        raise RuntimeError("Streaming API does not expose run/consume/start")

    if inspect.iscoroutinefunction(runner):
        task = asyncio.create_task(runner())
    else:
        # Offload sync runner to thread
        task = asyncio.create_task(asyncio.to_thread(runner))
    print("Stream started; waiting for events...")

    try:
        await asyncio.sleep(max(0, int(seconds)))
    finally:
        # Try graceful stop first
        stopped = False
        for stop_name in ("stop", "close", "disconnect"):
            fn = getattr(stream, stop_name, None)
            if callable(fn):
                try:
                    res = fn()
                    if asyncio.iscoroutine(res):
                        await res
                    stopped = True
                    break
                except Exception:
                    continue
        if not stopped and not task.done():
            task.cancel()
            try:
                await task
            except Exception:
                pass
        if fhandle:
            try:
                fhandle.flush()
                fhandle.close()
            except Exception:
                pass


def watch_stream(symbol: str, events: str = "trade", seconds: int = 30, feed: str = "iex", out_path: Optional[str] = None, append: bool = False) -> None:
    try:
        asyncio.run(_watch_async(symbol, events=events, seconds=seconds, feed=feed, out_path=out_path, append=append))
    except KeyboardInterrupt:
        print("Stopped.")


def maybe_place_order(client: TradingClient) -> Optional[str]:
    symbol = os.getenv("ALPACA_ORDER_SYMBOL")
    qty = os.getenv("ALPACA_ORDER_QTY")
    do_place = env_bool("ALPACA_PLACE_ORDER", False)

    if not do_place:
        return None

    if not symbol or not qty:
        raise RuntimeError(
            "Set ALPACA_ORDER_SYMBOL and ALPACA_ORDER_QTY to place an order, or unset ALPACA_PLACE_ORDER."
        )

    try:
        qty_i = int(qty)
    except ValueError as e:
        raise RuntimeError("ALPACA_ORDER_QTY must be an integer") from e

    order = MarketOrderRequest(
        symbol=symbol,
        qty=qty_i,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )

    submitted = client.submit_order(order)
    print("Submitted order:", submitted.id, submitted.symbol, submitted.qty, submitted.side)
    return str(submitted.id)


def place_test_aapl_order(client: TradingClient) -> str:
    order = MarketOrderRequest(
        symbol="AAPL",
        qty=1,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )

    submitted = client.submit_order(order)
    print("Submitted test order:", submitted.id, submitted.symbol, submitted.qty, submitted.side)
    return str(submitted.id)


def place_order(
    client: TradingClient,
    *,
    symbol: str,
    side: str = "buy",
    qty: Optional[int] = None,
    notional: Optional[float] = None,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    time_in_force: str = "day",
    order_class: Optional[str] = None,
    take_profit: Optional[float] = None,
    stop_loss: Optional[float] = None,
    stop_loss_limit: Optional[float] = None,
) -> str:
    # Normalize inputs
    sym = symbol.upper()
    s = side.strip().lower()
    tif_map = {
        "day": TimeInForce.DAY,
        "gtc": TimeInForce.GTC,
        "opg": TimeInForce.OPG,
        "cls": TimeInForce.CLS,
        "ioc": TimeInForce.IOC,
        "fok": TimeInForce.FOK,
    }
    tif = tif_map.get(time_in_force.lower(), TimeInForce.DAY)
    side_enum = OrderSide.BUY if s == "buy" else OrderSide.SELL

    # Build request
    otype = order_type.strip().lower()
    oc = None
    if order_class and order_class.strip().lower() == "bracket":
        if OrderClass is None:
            oc = "bracket"  # type: ignore[assignment]
        else:
            oc = OrderClass.BRACKET  # type: ignore[assignment]

    if otype == "market":
        if qty is None and notional is None:
            raise RuntimeError("For market orders, provide either qty or notional")
        kwargs = dict(symbol=sym, qty=qty, notional=notional, side=side_enum, time_in_force=tif)
        # Bracket support for market
        if oc is not None:
            if qty is None:
                raise RuntimeError("Bracket orders require --qty (notional not supported)")
            if (take_profit is None) or (stop_loss is None):
                raise RuntimeError("Bracket orders require --take-profit and --stop-loss")
            if TakeProfitRequest is None or StopLossRequest is None:
                raise RuntimeError("Bracket orders not supported by current alpaca-py version")
            kwargs.update(
                order_class=oc,
                take_profit=TakeProfitRequest(limit_price=float(take_profit)),  # type: ignore[arg-type]
                stop_loss=StopLossRequest(
                    stop_price=float(stop_loss),
                    limit_price=(None if stop_loss_limit is None else float(stop_loss_limit)),
                ),  # type: ignore[arg-type]
            )
        req = MarketOrderRequest(**kwargs)
    elif otype == "limit":
        if LimitOrderRequest is None:
            raise RuntimeError("Limit orders not supported by current alpaca-py version")
        if qty is None or limit_price is None:
            raise RuntimeError("Limit order requires qty and --limit-price")
        kwargs = dict(
            symbol=sym,
            qty=qty,
            limit_price=float(limit_price),
            side=side_enum,
            time_in_force=tif,
        )
        if oc is not None:
            if (take_profit is None) or (stop_loss is None):
                raise RuntimeError("Bracket limit requires --take-profit and --stop-loss")
            if TakeProfitRequest is None or StopLossRequest is None:
                raise RuntimeError("Bracket orders not supported by current alpaca-py version")
            kwargs.update(
                order_class=oc,
                take_profit=TakeProfitRequest(limit_price=float(take_profit)),  # type: ignore[arg-type]
                stop_loss=StopLossRequest(
                    stop_price=float(stop_loss),
                    limit_price=(None if stop_loss_limit is None else float(stop_loss_limit)),
                ),  # type: ignore[arg-type]
            )
        req = LimitOrderRequest(**kwargs)  # type: ignore[call-arg]
    elif otype == "stop":
        if StopOrderRequest is None:
            raise RuntimeError("Stop orders not supported by current alpaca-py version")
        if qty is None or stop_price is None:
            raise RuntimeError("Stop order requires --qty and --stop-price")
        req = StopOrderRequest(  # type: ignore[call-arg]
            symbol=sym,
            qty=qty,
            stop_price=float(stop_price),
            side=side_enum,
            time_in_force=tif,
        )
    elif otype in ("stop_limit", "stop-limit"):
        if StopLimitOrderRequest is None:
            raise RuntimeError("Stop-limit orders not supported by current alpaca-py version")
        if qty is None or stop_price is None or limit_price is None:
            raise RuntimeError("Stop-limit requires --qty, --stop-price and --limit-price")
        req = StopLimitOrderRequest(  # type: ignore[call-arg]
            symbol=sym,
            qty=qty,
            stop_price=float(stop_price),
            limit_price=float(limit_price),
            side=side_enum,
            time_in_force=tif,
        )
    else:
        raise RuntimeError("Unsupported order type. Use 'market' or 'limit'.")

    submitted = client.submit_order(req)
    print(
        "Submitted order:",
        submitted.id,
        submitted.symbol,
        submitted.qty,
        submitted.side,
        getattr(submitted, "limit_price", ""),
    )
    return str(submitted.id)


def place_oco_order(
    client: TradingClient,
    *,
    symbol: str,
    side: str,
    qty: int,
    take_profit: float,
    stop_loss: float,
    stop_loss_limit: Optional[float] = None,
    time_in_force: str = "day",
) -> str:
    sym = symbol.upper()
    s = side.strip().lower()
    if s not in ("buy", "sell"):
        raise RuntimeError("--side must be buy or sell for OCO")
    if qty <= 0:
        raise RuntimeError("--qty must be > 0 for OCO")

    tif_map = {
        "day": TimeInForce.DAY,
        "gtc": TimeInForce.GTC,
        "opg": TimeInForce.OPG,
        "cls": TimeInForce.CLS,
        "ioc": TimeInForce.IOC,
        "fok": TimeInForce.FOK,
    }
    tif = tif_map.get(time_in_force.lower(), TimeInForce.DAY)
    side_enum = OrderSide.BUY if s == "buy" else OrderSide.SELL

    if OrderClass is None or TakeProfitRequest is None or StopLossRequest is None:
        raise RuntimeError("OCO orders not supported by current alpaca-py version")

    req = MarketOrderRequest(
        symbol=sym,
        qty=qty,
        side=side_enum,
        time_in_force=tif,
        order_class=(OrderClass.OCO if hasattr(OrderClass, "OCO") else "oco"),  # type: ignore[arg-type]
        take_profit=TakeProfitRequest(limit_price=float(take_profit)),  # type: ignore[arg-type]
        stop_loss=StopLossRequest(
            stop_price=float(stop_loss),
            limit_price=(None if stop_loss_limit is None else float(stop_loss_limit)),
        ),  # type: ignore[arg-type]
    )
    submitted = client.submit_order(req)
    print("Submitted OCO:", submitted.id, submitted.symbol, submitted.qty, submitted.side)
    return str(submitted.id)


def place_test_aapl_sell_order(client: TradingClient) -> str:
    order = MarketOrderRequest(
        symbol="AAPL",
        qty=1,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )

    submitted = client.submit_order(order)
    print("Submitted test sell order:", submitted.id, submitted.symbol, submitted.qty, submitted.side)
    return str(submitted.id)


def main(argv: list[str]) -> int:
    try:
        client = get_client()
    except Exception as exc:
        print(f"Error: {exc}")
        return 2

    try:
        show_account_summary(client)
        if "--positions" in argv:
            list_positions(client)
            order_id = None
        elif "--position" in argv:
            try:
                sym = argv[argv.index("--position") + 1]
            except (ValueError, IndexError):
                print("Usage: --position <SYMBOL>")
                return 2
            show_position(client, sym)
            order_id = None
        elif "--orders" in argv:
            # Optional filters: --limit N, --status <open|closed|all>, --side <buy|sell>
            def _opt_val(flag: str) -> Optional[str]:
                if flag in argv:
                    try:
                        return argv[argv.index(flag) + 1]
                    except (ValueError, IndexError):
                        return None
                return None

            limit_val = _opt_val("--limit")
            status_val = _opt_val("--status")
            side_val = _opt_val("--side")
            limit_int = None
            if limit_val is not None:
                try:
                    limit_int = int(limit_val)
                except ValueError:
                    print("--limit must be an integer")
                    return 2

            list_orders(client, limit=limit_int, status=status_val, side=side_val)
            order_id = None
        elif "--history" in argv:
            def _opt_val_h(flag: str) -> Optional[str]:
                if flag in argv:
                    try:
                        return argv[argv.index(flag) + 1]
                    except (ValueError, IndexError):
                        return None
                return None
            sym = _opt_val_h("--symbol")
            bars = _opt_val_h("--bars")
            tf = _opt_val_h("--timeframe")
            if not sym:
                print("Usage: --history --symbol <SYM> [--bars N] [--timeframe 1Min|5Min|1Day]")
                return 2
            try:
                limit = int(bars) if bars is not None else 30
            except ValueError:
                print("--bars must be an integer")
                return 2
            show_history_bars(sym, limit=limit, timeframe=tf)
            order_id = None
        elif "--watch" in argv:
            def _opt_val_w(flag: str) -> Optional[str]:
                if flag in argv:
                    try:
                        return argv[argv.index(flag) + 1]
                    except (ValueError, IndexError):
                        return None
                return None
            sym = _opt_val_w("--symbol")
            ev = _opt_val_w("--events") or "trade"
            secs = _opt_val_w("--seconds")
            feed = _opt_val_w("--feed") or "iex"
            outp = _opt_val_w("--out")
            append = "--append" in argv
            if not sym:
                print("Usage: --watch --symbol <SYM> [--events trade|quote|bar] [--seconds N] [--feed iex|sip]")
                return 2
            try:
                seconds = int(secs) if secs is not None else 30
            except ValueError:
                print("--seconds must be an integer")
                return 2
            watch_stream(sym, events=ev, seconds=seconds, feed=feed, out_path=outp, append=append)
            order_id = None
        elif "--order" in argv:
            def _req_val(flag: str) -> Optional[str]:
                if flag in argv:
                    try:
                        return argv[argv.index(flag) + 1]
                    except (ValueError, IndexError):
                        return None
                return None

            sym = _req_val("--symbol")
            qty_s = _req_val("--qty")
            notional_s = _req_val("--notional")
            side_s = _req_val("--side") or "buy"
            type_s = _req_val("--type") or "market"
            tif_s = _req_val("--tif") or "day"
            lmt_s = _req_val("--limit-price")
            stp_s = _req_val("--stop-price")
            oc_s = _req_val("--order-class")
            tp_s = _req_val("--take-profit")
            sl_s = _req_val("--stop-loss")
            sll_s = _req_val("--stop-loss-limit")

            if not sym:
                print("Usage: --order --symbol <SYM> [--qty N | --notional X] [--side buy|sell] [--type market|limit] [--limit-price P] [--tif day|gtc|opg|cls|ioc|fok]")
                return 2

            qty_i = None
            notional_f = None
            if qty_s is not None:
                try:
                    qty_i = int(qty_s)
                except ValueError:
                    print("--qty must be an integer")
                    return 2
            if notional_s is not None:
                try:
                    notional_f = float(notional_s)
                except ValueError:
                    print("--notional must be a number")
                    return 2
            limit_f = None
            if lmt_s is not None:
                try:
                    limit_f = float(lmt_s)
                except ValueError:
                    print("--limit-price must be a number")
                    return 2
            stop_f = None
            if stp_s is not None:
                try:
                    stop_f = float(stp_s)
                except ValueError:
                    print("--stop-price must be a number")
                    return 2
            tp_f = None
            if tp_s is not None:
                try:
                    tp_f = float(tp_s)
                except ValueError:
                    print("--take-profit must be a number")
                    return 2
            sl_f = None
            if sl_s is not None:
                try:
                    sl_f = float(sl_s)
                except ValueError:
                    print("--stop-loss must be a number")
                    return 2
            sll_f = None
            if sll_s is not None:
                try:
                    sll_f = float(sll_s)
                except ValueError:
                    print("--stop-loss-limit must be a number")
                    return 2

            order_id = place_order(
                client,
                symbol=sym,
                side=side_s,
                qty=qty_i,
                notional=notional_f,
                order_type=type_s,
                limit_price=limit_f,
                stop_price=stop_f,
                time_in_force=tif_s,
                order_class=oc_s,
                take_profit=tp_f,
                stop_loss=sl_f,
                stop_loss_limit=sll_f,
            )
        elif "--oco" in argv:
            def _req_val2(flag: str) -> Optional[str]:
                if flag in argv:
                    try:
                        return argv[argv.index(flag) + 1]
                    except (ValueError, IndexError):
                        return None
                return None

            sym = _req_val2("--symbol")
            qty_s = _req_val2("--qty")
            side_s = _req_val2("--side") or "sell"
            tif_s = _req_val2("--tif") or "day"
            tp_s = _req_val2("--take-profit")
            sl_s = _req_val2("--stop-loss")
            sll_s = _req_val2("--stop-loss-limit")

            if not sym or tp_s is None or sl_s is None or qty_s is None:
                print("Usage: --oco --symbol <SYM> --qty <N> [--side buy|sell] --take-profit <P> --stop-loss <P> [--stop-loss-limit <P>] [--tif ...]")
                return 2

            try:
                qty_i = int(qty_s)
            except ValueError:
                print("--qty must be an integer")
                return 2

            try:
                tp_f = float(tp_s)
                sl_f = float(sl_s)
            except ValueError:
                print("--take-profit and --stop-loss must be numbers")
                return 2

            sll_f = None
            if sll_s is not None:
                try:
                    sll_f = float(sll_s)
                except ValueError:
                    print("--stop-loss-limit must be a number")
                    return 2

            order_id = place_oco_order(
                client,
                symbol=sym,
                side=side_s,
                qty=qty_i,
                take_profit=tp_f,
                stop_loss=sl_f,
                stop_loss_limit=sll_f,
                time_in_force=tif_s,
            )
        elif "--close-position" in argv:
            try:
                sym = argv[argv.index("--close-position") + 1]
            except (ValueError, IndexError):
                print("Usage: --close-position <SYMBOL>")
                return 2
            close_position_symbol(client, sym)
            order_id = None
        elif "--flatten-all" in argv:
            close_all_positions(client)
            order_id = None
        elif "--cancel" in argv:
            try:
                oid = argv[argv.index("--cancel") + 1]
            except (ValueError, IndexError):
                print("Usage: --cancel <ORDER_ID>")
                return 2
            cancel_order_id(client, oid)
            order_id = None
        elif "--cancel-all" in argv:
            cancel_all_orders(client)
            order_id = None
        elif "--order-status" in argv:
            try:
                oid = argv[argv.index("--order-status") + 1]
            except (ValueError, IndexError):
                print("Usage: --order-status <ORDER_ID>")
                return 2
            show_order_status(client, oid)
            order_id = None
        elif "--sell-test-order" in argv:
            order_id = place_test_aapl_sell_order(client)
        elif "--test-order" in argv:
            order_id = place_test_aapl_order(client)
        else:
            order_id = maybe_place_order(client)
        if order_id:
            print("Order ID:", order_id)
    except Exception as exc:
        print(f"API error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
