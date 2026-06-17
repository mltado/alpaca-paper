# Alpaca Paper CLI

Small helper script to connect to Alpaca (paper) and perform common tasks: view account, list positions/orders, place/cancel orders, and manage positions.

## Setup

1) Copy the env template and add your paper keys

```powershell
Copy-Item alpaca-paper\.env.example alpaca-paper\.env
```

Edit `alpaca-paper/.env` and set:
- `ALPACA_API_KEY_ID`
- `ALPACA_API_SECRET_KEY`
- `ALPACA_USE_PAPER=true`

2) Run with your venv’s Python

```powershell
c:/Users/mltad/OneDrive/VSCode/.venv/Scripts/python.exe alpaca-paper/connect.py --positions
```

## Commands

- Account + summary (always prints on start)
  ```powershell
  .../python.exe alpaca-paper/connect.py
  ```

- List positions
  ```powershell
  .../python.exe alpaca-paper/connect.py --positions
  ```

- Show one position
  ```powershell
  .../python.exe alpaca-paper/connect.py --position AAPL
  ```

- List orders (with filters)
  ```powershell
  # last 5
  .../python.exe alpaca-paper/connect.py --orders --limit 5
  # only open
  .../python.exe alpaca-paper/connect.py --orders --status open
  # closed sells
  .../python.exe alpaca-paper/connect.py --orders --status closed --side sell
  ```

- Show one order’s status
  ```powershell
  .../python.exe alpaca-paper/connect.py --order-status <ORDER_ID>
  ```

- Cancel orders
  ```powershell
  .../python.exe alpaca-paper/connect.py --cancel <ORDER_ID>
  .../python.exe alpaca-paper/connect.py --cancel-all
  ```

- Place basic orders
  ```powershell
  # Market buy 1 AAPL
  .../python.exe alpaca-paper/connect.py --order --symbol AAPL --qty 1 --side buy --type market

  # Market notional buy $100 AAPL
  .../python.exe alpaca-paper/connect.py --order --symbol AAPL --notional 100 --side buy --type market

  # Limit sell 1 AAPL @ 250, GTC
  .../python.exe alpaca-paper/connect.py --order --symbol AAPL --qty 1 --side sell --type limit --limit-price 250 --tif gtc
  ```

- Stop and stop‑limit orders
  ```powershell
  # Stop: trigger at 180 to sell 1 share
  .../python.exe alpaca-paper/connect.py --order --symbol AAPL --qty 1 --side sell --type stop --stop-price 180

  # Stop‑limit: trigger 180, place limit sell at 179.5
  .../python.exe alpaca-paper/connect.py --order --symbol AAPL --qty 1 --side sell --type stop-limit --stop-price 180 --limit-price 179.5
  ```

- Bracket orders (entry with attached TP/SL)
  ```powershell
  # Market entry + TP/SL
  .../python.exe alpaca-paper/connect.py --order --symbol AAPL --qty 1 --side buy --type market --order-class bracket --take-profit 205 --stop-loss 190

  # Limit entry 195 + TP/SL (SL as stop‑limit 187.5)
  .../python.exe alpaca-paper/connect.py --order --symbol AAPL --qty 1 --side buy --type limit --limit-price 195 --order-class bracket --take-profit 210 --stop-loss 188 --stop-loss-limit 187.5
  ```

- OCO exit orders (no entry) — take‑profit and stop‑loss pair (OCO)
  ```powershell
  # Sell 1 with TP 205 and SL 190 (OCO)
  .../python.exe alpaca-paper/connect.py --oco --symbol AAPL --qty 1 --side sell --take-profit 205 --stop-loss 190
  # Optional: SL as stop‑limit
  .../python.exe alpaca-paper/connect.py --oco --symbol AAPL --qty 1 --side sell --take-profit 205 --stop-loss 190 --stop-loss-limit 189.5
  ```

- Close positions
  ```powershell
  # Close one symbol
  .../python.exe alpaca-paper/connect.py --close-position AAPL
  # Close all symbols
  .../python.exe alpaca-paper/connect.py --flatten-all
  ```

- Quick test helpers
  ```powershell
  .../python.exe alpaca-paper/connect.py --test-order        # AAPL BUY 1
  .../python.exe alpaca-paper/connect.py --sell-test-order   # AAPL SELL 1
  ```

## History and Live Watch

- Recent bars (history)
  ```powershell
  # Last 30 daily bars (default timeframe 1Day)
  .../python.exe alpaca-paper/connect.py --history --symbol AAPL
  # Last 50 5-minute bars
  .../python.exe alpaca-paper/connect.py --history --symbol AAPL --bars 50 --timeframe 5Min
  ```

- Watch live stream
  ```powershell
  # Live trades for 30s (default feed iex)
  .../python.exe alpaca-paper/connect.py --watch --symbol AAPL --events trade --seconds 30
  # Live quotes for 60s using SIP feed (requires plan)
  .../python.exe alpaca-paper/connect.py --watch --symbol AAPL --events quote --seconds 60 --feed sip
  ```

- Watch and log to CSV (longer runs)
  ```powershell
  # Stream trades for 5 minutes and save to watch.csv (overwrite)
  .../python.exe alpaca-paper/connect.py --watch --symbol SPY --events trade --seconds 300 --out alpaca-paper\watch.csv

  # Append to an existing CSV instead of overwriting
  .../python.exe alpaca-paper/connect.py --watch --symbol SPY --events quote --seconds 300 --out alpaca-paper\watch.csv --append
  ```

### Minimal code samples

- Historical bars
  ```python
  from alpaca.data.historical import StockHistoricalDataClient
  from alpaca.data.requests import StockBarsRequest
  from alpaca.data.timeframe import TimeFrame
  import os
  from dotenv import load_dotenv

  load_dotenv("alpaca-paper/.env")
  client = StockHistoricalDataClient(os.getenv("ALPACA_API_KEY_ID"), os.getenv("ALPACA_API_SECRET_KEY"))
  bars = client.get_stock_bars(StockBarsRequest(symbol_or_symbols="AAPL", timeframe=TimeFrame.Day, limit=5))
  for b in list(bars["AAPL"]):
      print(b.timestamp, b.open, b.high, b.low, b.close, b.volume)
  ```

- Live trades
  ```python
  import asyncio
  from alpaca.data.live import StockDataStream
  import os
  from dotenv import load_dotenv

  load_dotenv("alpaca-paper/.env")
  stream = StockDataStream(os.getenv("ALPACA_API_KEY_ID"), os.getenv("ALPACA_API_SECRET_KEY"), feed="iex")

  async def on_trade(t):
      print("TRADE", t.symbol, t.price, t.size, t.timestamp)

  async def main():
      stream.subscribe_trades(on_trade, "AAPL")
      await asyncio.wait_for(stream.consume(), timeout=10)

  asyncio.run(main())
  ```

## Minimal Python example

```python
from dotenv import load_dotenv
import os
from alpaca.trading.client import TradingClient

load_dotenv("alpaca-paper/.env")
client = TradingClient(os.getenv("ALPACA_API_KEY_ID"), os.getenv("ALPACA_API_SECRET_KEY"), paper=True)

for p in client.get_all_positions() or []:
    print(p.symbol, p.qty, p.market_value)
```

## Notes
- Paper trading only by default (`ALPACA_USE_PAPER=true`).
- Some features (limit/stop/bracket/OCO) require alpaca‑py versions that expose the corresponding request classes and enums. The script prints a clear message if unsupported.
