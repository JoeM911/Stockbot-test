import asyncio
import os
from contextlib import asynccontextmanager
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from alpaca_client import AlpacaClient
from indicators import compute_indicators
from news import fetch_news
import mock_data
from scanner import Scanner
from target_manager import TargetManager
from auto_trader import AutoTrader
from sentiment import SentimentAnalyzer
from strategies.day_trader import DayTrader
from strategies.swing_trader import SwingTrader

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY", "")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
DEMO_MODE = API_KEY in ("", "placeholder", "your_api_key_here")

alpaca = AlpacaClient(API_KEY, SECRET_KEY)
scanner = Scanner(alpaca)
target_mgr = TargetManager()
day_trader = DayTrader(alpaca)
swing_trader = SwingTrader(alpaca)
sentiment_analyzer = SentimentAnalyzer()
auto_trader = AutoTrader(alpaca, scanner, sentiment_analyzer)

# In-memory equity history for demo mode / live tracking (capped at 1440 pts)
_equity_history: List[dict] = []

# Expanded universe — more stocks = more signals for the auto-trader
UNIVERSE: List[str] = [
    "AAPL","MSFT","NVDA","TSLA","GOOGL","META","AMZN","AMD","SPY","QQQ",
    "PLTR","SOFI","COIN","NFLX","CRM","UBER","SNAP","RBLX","HOOD","RIVN",
    "NIO","XPEV","MSTR","MARA","RIOT","SMCI","ARM","AVGO","MU","TSM",
    "INTC","ORCL","IBM","ABNB","DKNG","PENN","LCID","F","GM","GE",
    "BAC","JPM","GS","MS","WFC","XOM","CVX","OXY","SLB","HAL",
]

WATCHLIST: List[str] = os.getenv(
    "WATCHLIST",
    "AAPL,MSFT,NVDA,TSLA,GOOGL,META,AMD,SPY,QQQ,AMZN,PLTR,SOFI,COIN",
).split(",")


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self._active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._active:
            self._active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in list(self._active):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self._active:
                self._active.remove(ws)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Background loops
# ---------------------------------------------------------------------------

async def broadcast_loop():
    _last_equity_record = 0.0
    while True:
        try:
            if DEMO_MODE:
                account  = mock_data.get_account()
                positions = mock_data.get_positions()
                orders   = mock_data.get_recent_orders()
                quotes   = mock_data.get_latest_quotes(WATCHLIST)
            else:
                account, positions, orders = await asyncio.gather(
                    alpaca.get_account(),
                    alpaca.get_positions(),
                    alpaca.get_recent_orders(),
                )
                quotes = await alpaca.get_latest_quotes(WATCHLIST)

            await manager.broadcast({"type": "account", "data": account})
            await manager.broadcast({"type": "positions", "data": positions})
            await manager.broadcast({"type": "orders", "data": orders})
            await manager.broadcast({"type": "quotes", "data": quotes})

            hits = target_mgr.check_targets(quotes)
            for hit in hits:
                await manager.broadcast({"type": "target_hit", "data": hit})

            # Record equity every 5 minutes
            import time as _time
            now_ts = _time.time()
            if now_ts - _last_equity_record >= 300 and account:
                eq = account.get("equity") or account.get("portfolio_value")
                if eq:
                    _equity_history.append({"time": int(now_ts), "value": round(float(eq), 2)})
                    if len(_equity_history) > 1440:
                        _equity_history.pop(0)
                _last_equity_record = now_ts

        except Exception as e:
            print(f"[broadcast_loop] {e}")
        await asyncio.sleep(3)


async def scanner_loop():
    while True:
        try:
            if DEMO_MODE:
                signals = mock_data.get_scanner_signals(UNIVERSE)
            else:
                signals = await scanner.scan(UNIVERSE)
            if signals:
                await manager.broadcast({"type": "signals", "data": signals})
        except Exception as e:
            print(f"[scanner_loop] {e}")
        await asyncio.sleep(60)


async def auto_trader_loop():
    while True:
        try:
            if not DEMO_MODE:
                await auto_trader.run(UNIVERSE, manager)
        except Exception as e:
            print(f"[auto_trader_loop] {e}")
        await asyncio.sleep(60)


async def sentiment_loop():
    while True:
        try:
            trending  = await sentiment_analyzer.get_trending()
            reddit    = await sentiment_analyzer.get_reddit_mentions()
            # Score sentiment for trending + top universe symbols
            hot_syms  = list({s["symbol"] for s in trending[:10]} |
                             set(UNIVERSE[:20]))
            scores    = await sentiment_analyzer.scan_sentiment(hot_syms)
            await manager.broadcast({
                "type": "sentiment",
                "data": {
                    "scores":   scores,
                    "trending": trending[:15],
                    "reddit":   reddit[:15],
                },
            })
        except Exception as e:
            print(f"[sentiment_loop] {e}")
        await asyncio.sleep(300)  # every 5 minutes


async def strategy_loop():
    while True:
        try:
            mode = os.getenv("TRADING_MODE", "manual").lower()
            if mode in ("day", "all"):
                await day_trader.run(WATCHLIST)
            if mode in ("swing", "all"):
                await swing_trader.run(WATCHLIST)
        except Exception as e:
            print(f"[strategy_loop] {e}")
        await asyncio.sleep(60)


async def news_loop():
    while True:
        try:
            if DEMO_MODE:
                news = mock_data.get_news(WATCHLIST[:8])
            else:
                news = await fetch_news(API_KEY, SECRET_KEY, WATCHLIST[:8])
            await manager.broadcast({"type": "news", "data": news})
        except Exception as e:
            print(f"[news_loop] {e}")
        await asyncio.sleep(120)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(broadcast_loop())
    asyncio.create_task(scanner_loop())
    asyncio.create_task(auto_trader_loop())
    asyncio.create_task(sentiment_loop())
    asyncio.create_task(strategy_loop())
    asyncio.create_task(news_loop())
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="StockBot Terminal", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "subscribe":
                symbol = data.get("symbol", "AAPL").upper()
                tf = data.get("timeframe", "1D")
                bars = mock_data.get_bars(symbol, tf, 200) if DEMO_MODE else await alpaca.get_bars(symbol, tf, 200)
                indicators = compute_indicators(bars)
                await ws.send_json({
                    "type": "chart",
                    "symbol": symbol,
                    "bars": bars,
                    "indicators": indicators,
                })
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/account")
async def get_account():
    return mock_data.get_account() if DEMO_MODE else await alpaca.get_account()


@app.get("/api/positions")
async def get_positions():
    return mock_data.get_positions() if DEMO_MODE else await alpaca.get_positions()


@app.get("/api/orders")
async def get_orders():
    return mock_data.get_recent_orders() if DEMO_MODE else await alpaca.get_recent_orders()


@app.get("/api/bars/{symbol}")
async def get_bars(symbol: str, timeframe: str = "1D", limit: int = 200):
    bars = mock_data.get_bars(symbol.upper(), timeframe, limit) if DEMO_MODE else await alpaca.get_bars(symbol.upper(), timeframe, limit)
    indicators = compute_indicators(bars)
    return {"bars": bars, "indicators": indicators}

@app.get("/api/demo-mode")
async def demo_mode_status():
    return {"demo": DEMO_MODE}


class OrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str
    type: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None
    time_in_force: str = "day"


@app.post("/api/orders")
async def place_order(req: OrderRequest):
    if DEMO_MODE:
        result = {"id": "demo-" + req.symbol, "symbol": req.symbol.upper(),
                  "qty": req.qty, "side": req.side, "type": req.type, "status": "filled"}
    else:
        result = await alpaca.place_order(
            req.symbol.upper(), req.qty, req.side,
            req.type, req.limit_price, req.stop_price, req.time_in_force,
        )
    await manager.broadcast({"type": "order_placed", "data": result})
    return result


@app.delete("/api/orders/{order_id}")
async def cancel_order(order_id: str):
    if DEMO_MODE:
        return {"id": order_id, "status": "canceled"}
    return await alpaca.cancel_order(order_id)


class TargetRequest(BaseModel):
    symbol: str
    target_price: float
    target_type: str = "above"
    note: str = ""


@app.post("/api/targets")
async def add_target(req: TargetRequest):
    return target_mgr.add_target(req.symbol, req.target_price, req.target_type, req.note)


@app.get("/api/targets")
async def get_targets():
    return target_mgr.get_all()


@app.delete("/api/targets/{target_id}")
async def delete_target(target_id: str):
    return target_mgr.remove_target(target_id)


@app.get("/api/watchlist")
async def get_watchlist():
    return WATCHLIST


@app.post("/api/watchlist/{symbol}")
async def add_watchlist(symbol: str):
    s = symbol.upper()
    if s not in WATCHLIST:
        WATCHLIST.append(s)
    return WATCHLIST


@app.delete("/api/watchlist/{symbol}")
async def remove_watchlist(symbol: str):
    s = symbol.upper()
    if s in WATCHLIST:
        WATCHLIST.remove(s)
    return WATCHLIST


@app.get("/api/news")
async def get_news():
    return mock_data.get_news(WATCHLIST[:8]) if DEMO_MODE else await fetch_news(API_KEY, SECRET_KEY, WATCHLIST[:8])


@app.get("/api/scanner")
async def get_scanner():
    return mock_data.get_scanner_signals(UNIVERSE) if DEMO_MODE else await scanner.scan(UNIVERSE)


@app.get("/api/portfolio/history")
async def portfolio_history(period: str = "1M"):
    if DEMO_MODE:
        # Synthesise a growth curve from in-memory points or generate fake history
        if len(_equity_history) >= 2:
            return _equity_history
        return mock_data.get_portfolio_history(period)
    try:
        return await alpaca.get_portfolio_history(period)
    except Exception as e:
        print(f"[portfolio_history] {e}")
        return _equity_history


@app.get("/api/sentiment")
async def get_sentiment():
    trending = await sentiment_analyzer.get_trending()
    reddit   = await sentiment_analyzer.get_reddit_mentions()
    hot_syms = list({s["symbol"] for s in trending[:10]} | set(UNIVERSE[:20]))
    scores   = await sentiment_analyzer.scan_sentiment(hot_syms)
    return {"scores": scores, "trending": trending[:15], "reddit": reddit[:15]}


@app.get("/api/bot/status")
async def bot_status():
    return auto_trader.get_status()


@app.post("/api/bot/toggle")
async def bot_toggle():
    enabled = auto_trader.toggle()
    await manager.broadcast({"type": "bot_status", "data": auto_trader.get_status()})
    return {"enabled": enabled}


class BotSettingsRequest(BaseModel):
    max_positions: int | None = None
    risk_pct: float | None = None
    stop_pct: float | None = None
    target_pct: float | None = None


@app.post("/api/bot/settings")
async def bot_settings(req: BotSettingsRequest):
    if req.max_positions is not None:
        auto_trader.max_positions = max(1, min(req.max_positions, 20))
    if req.risk_pct is not None:
        auto_trader.risk_pct = max(0.01, min(req.risk_pct, 0.25))
    if req.stop_pct is not None:
        auto_trader.stop_pct = max(0.01, min(req.stop_pct, 0.20))
    if req.target_pct is not None:
        auto_trader.target_pct = max(0.01, min(req.target_pct, 0.50))
    await manager.broadcast({"type": "bot_status", "data": auto_trader.get_status()})
    return auto_trader.get_status()


class CommandRequest(BaseModel):
    command: str


@app.post("/api/command")
async def process_command(req: CommandRequest):
    """Bloomberg-style terminal commands: BUY AAPL 10 | SELL TSLA 5 | TARGET AAPL 200 | ADD NVDA | REMOVE NVDA"""
    parts = req.command.upper().strip().split()
    if not parts:
        return {"error": "Empty command"}

    cmd = parts[0]

    try:
        if cmd == "BUY" and len(parts) >= 3:
            sym, qty = parts[1], float(parts[2])
            order_type = parts[3] if len(parts) > 3 else "market"
            limit_price = float(parts[4]) if len(parts) > 4 else None
            if DEMO_MODE:
                result = {"id": f"demo-{sym}", "symbol": sym, "qty": qty, "side": "buy", "type": order_type.lower(), "status": "filled"}
            else:
                result = await alpaca.place_order(sym, qty, "buy", order_type.lower(), limit_price)
            await manager.broadcast({"type": "order_placed", "data": result})
            return {"ok": True, "message": f"BUY {qty} {sym}", "order": result}

        elif cmd == "SELL" and len(parts) >= 3:
            sym, qty = parts[1], float(parts[2])
            order_type = parts[3] if len(parts) > 3 else "market"
            limit_price = float(parts[4]) if len(parts) > 4 else None
            if DEMO_MODE:
                result = {"id": f"demo-{sym}", "symbol": sym, "qty": qty, "side": "sell", "type": order_type.lower(), "status": "filled"}
            else:
                result = await alpaca.place_order(sym, qty, "sell", order_type.lower(), limit_price)
            await manager.broadcast({"type": "order_placed", "data": result})
            return {"ok": True, "message": f"SELL {qty} {sym}", "order": result}

        elif cmd == "TARGET" and len(parts) >= 3:
            sym, price = parts[1], float(parts[2])
            direction = parts[3].lower() if len(parts) > 3 else "above"
            target = target_mgr.add_target(sym, price, direction)
            return {"ok": True, "message": f"Target set: {sym} @ ${price} ({direction})", "target": target}

        elif cmd == "ADD" and len(parts) >= 2:
            sym = parts[1]
            if sym not in WATCHLIST:
                WATCHLIST.append(sym)
            return {"ok": True, "message": f"Added {sym} to watchlist"}

        elif cmd == "REMOVE" and len(parts) >= 2:
            sym = parts[1]
            if sym in WATCHLIST:
                WATCHLIST.remove(sym)
            return {"ok": True, "message": f"Removed {sym} from watchlist"}

        elif cmd == "CLOSE" and len(parts) >= 2:
            sym = parts[1]
            if DEMO_MODE:
                positions = mock_data.get_positions()
            else:
                positions = await alpaca.get_positions()
            pos = next((p for p in positions if p["symbol"] == sym), None)
            if not pos:
                return {"error": f"No open position in {sym}"}
            if DEMO_MODE:
                result = {"id": f"demo-{sym}", "symbol": sym, "qty": pos["qty"], "side": "sell", "type": "market", "status": "filled"}
            else:
                result = await alpaca.place_order(sym, abs(pos["qty"]), "sell", "market")
            return {"ok": True, "message": f"Closing {sym}", "order": result}

        else:
            return {"error": f"Unknown command: {cmd}. Try: BUY AAPL 10 | SELL TSLA 5 | TARGET AAPL 200 | ADD SPY | CLOSE NVDA"}

    except Exception as e:
        return {"error": str(e)}
