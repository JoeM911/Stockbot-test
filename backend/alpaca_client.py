import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest, StopOrderRequest,
    StopLimitOrderRequest, GetOrdersRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit


class AlpacaClient:
    def __init__(self, api_key: str, secret_key: str):
        self.trading = TradingClient(api_key, secret_key, paper=True)
        self.data = StockHistoricalDataClient(api_key, secret_key)
        self.api_key = api_key
        self.secret_key = secret_key

    async def get_account(self) -> dict:
        account = await asyncio.to_thread(self.trading.get_account)
        equity = float(account.equity)
        last_equity = float(account.last_equity)
        pnl = equity - last_equity
        return {
            "equity": equity,
            "buying_power": float(account.buying_power),
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "day_trade_count": account.daytrade_count,
            "pnl": pnl,
            "pnl_pct": (pnl / last_equity * 100) if last_equity else 0,
            "pattern_day_trader": account.pattern_day_trader,
        }

    async def get_positions(self) -> List[dict]:
        positions = await asyncio.to_thread(self.trading.get_all_positions)
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price or 0),
                "market_value": float(p.market_value or 0),
                "unrealized_pl": float(p.unrealized_pl or 0),
                "unrealized_plpc": float(p.unrealized_plpc or 0) * 100,
                "side": p.side.value,
                "cost_basis": float(p.cost_basis or 0),
            }
            for p in positions
        ]

    async def get_recent_orders(self, limit: int = 20) -> List[dict]:
        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit)
        orders = await asyncio.to_thread(self.trading.get_orders, filter=req)
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "qty": float(o.qty or 0),
                "filled_qty": float(o.filled_qty or 0),
                "side": o.side.value,
                "type": o.order_type.value,
                "status": o.status.value,
                "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
                "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
            }
            for o in orders
        ]

    async def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
        extended_hours: bool = False,
        use_current_price: bool = False,
    ) -> dict:
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        tif = TimeInForce.DAY if time_in_force.lower() == "day" else TimeInForce.GTC

        # Extended hours requires limit orders on Alpaca
        if extended_hours:
            if use_current_price or limit_price is None:
                # Fetch latest quote to set a tight limit price
                try:
                    from alpaca.data.requests import StockLatestQuoteRequest
                    req_q = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
                    quotes = await asyncio.to_thread(self.data.get_stock_latest_quote, req_q)
                    q = quotes.get(symbol) or quotes[symbol]
                    mid = (float(q.bid_price) + float(q.ask_price)) / 2
                    # Buy slightly above mid, sell slightly below
                    limit_price = round(mid * (1.003 if order_side == OrderSide.BUY else 0.997), 2)
                except Exception:
                    limit_price = limit_price or 0
            req = LimitOrderRequest(
                symbol=symbol, qty=qty, side=order_side,
                time_in_force=tif, limit_price=limit_price,
                extended_hours=True,
            )
        elif order_type == "limit" and limit_price:
            req = LimitOrderRequest(
                symbol=symbol, qty=qty, side=order_side,
                time_in_force=tif, limit_price=limit_price,
            )
        elif order_type == "stop" and stop_price:
            req = StopOrderRequest(
                symbol=symbol, qty=qty, side=order_side,
                time_in_force=tif, stop_price=stop_price,
            )
        elif order_type == "stop_limit" and limit_price and stop_price:
            req = StopLimitOrderRequest(
                symbol=symbol, qty=qty, side=order_side, time_in_force=tif,
                limit_price=limit_price, stop_price=stop_price,
            )
        else:
            req = MarketOrderRequest(symbol=symbol, qty=qty, side=order_side, time_in_force=tif)

        order = await asyncio.to_thread(self.trading.submit_order, req)
        return {
            "id": str(order.id),
            "symbol": order.symbol,
            "qty": float(order.qty),
            "side": order.side.value,
            "type": order.order_type.value,
            "status": order.status.value,
        }

    async def cancel_order(self, order_id: str) -> dict:
        await asyncio.to_thread(self.trading.cancel_order_by_id, order_id)
        return {"cancelled": order_id}

    def _get_timeframe(self, tf: str) -> TimeFrame:
        mapping = {
            "1m": TimeFrame(1, TimeFrameUnit.Minute),
            "5m": TimeFrame(5, TimeFrameUnit.Minute),
            "15m": TimeFrame(15, TimeFrameUnit.Minute),
            "30m": TimeFrame(30, TimeFrameUnit.Minute),
            "1H": TimeFrame(1, TimeFrameUnit.Hour),
            "4H": TimeFrame(4, TimeFrameUnit.Hour),
            "1D": TimeFrame(1, TimeFrameUnit.Day),
            "1W": TimeFrame(1, TimeFrameUnit.Week),
        }
        return mapping.get(tf, TimeFrame.Day)

    def _start_for_timeframe(self, tf: str, limit: int) -> datetime:
        now = datetime.now(timezone.utc)
        if tf in ("1m", "5m"):
            return now - timedelta(days=7)
        elif tf in ("15m", "30m"):
            return now - timedelta(days=30)
        elif tf == "1H":
            return now - timedelta(days=60)
        elif tf == "4H":
            return now - timedelta(days=120)
        else:
            return now - timedelta(days=max(limit * 2, 365))

    async def get_bars(self, symbol: str, timeframe: str = "1D", limit: int = 200) -> List[dict]:
        tf = self._get_timeframe(timeframe)
        start = self._start_for_timeframe(timeframe, limit)

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            limit=limit,
        )
        bars = await asyncio.to_thread(self.data.get_stock_bars, req)
        try:
            bar_list = bars[symbol]
        except (KeyError, TypeError):
            bar_list = []

        return [
            {
                "time": int(b.timestamp.timestamp()),
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "volume": float(b.volume),
            }
            for b in bar_list
        ]

    async def get_portfolio_history(self, period: str = "1M", timeframe: str = "1D") -> List[dict]:
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        tf_map = {"1D": "1H", "1W": "1D", "1M": "1D", "3M": "1D"}
        req = GetPortfolioHistoryRequest(
            period=period,
            timeframe=tf_map.get(period, "1D"),
            intraday_reporting="market_hours" if period == "1D" else None,
        )
        h = await asyncio.to_thread(self.trading.get_portfolio_history, filter=req)
        result = []
        for ts, eq in zip(h.timestamp, h.equity):
            if eq is not None and eq > 0:
                result.append({"time": int(ts.timestamp()) if hasattr(ts, "timestamp") else int(ts), "value": round(float(eq), 2)})
        return result

    async def get_latest_quotes(self, symbols: List[str]) -> Dict[str, dict]:
        if not symbols:
            return {}
        try:
            req = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = await asyncio.to_thread(self.data.get_stock_latest_quote, req)
            result = {}
            for symbol, q in quotes.items():
                bid = float(q.bid_price) if q.bid_price else 0
                ask = float(q.ask_price) if q.ask_price else 0
                price = (bid + ask) / 2 if (bid and ask) else bid or ask
                result[symbol] = {"symbol": symbol, "bid": bid, "ask": ask, "price": price}
            return result
        except Exception as e:
            print(f"Quote fetch error: {e}")
            return {}
