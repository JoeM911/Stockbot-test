import { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/Header';
import Chart from './components/Chart';
import Positions from './components/Positions';
import Orders from './components/Orders';
import NewsPanel from './components/NewsPanel';
import OrderEntry from './components/OrderEntry';
import TargetPanel from './components/TargetPanel';
import Scanner from './components/Scanner';
import Watchlist from './components/Watchlist';

const API = '';  // proxied via vite
const WS_URL = `ws://${window.location.host}/ws`;

export default function App() {
  const [account, setAccount]       = useState(null);
  const [positions, setPositions]   = useState([]);
  const [orders, setOrders]         = useState([]);
  const [quotes, setQuotes]         = useState({});
  const [news, setNews]             = useState([]);
  const [signals, setSignals]       = useState([]);
  const [targets, setTargets]       = useState([]);
  const [alerts, setAlerts]         = useState([]);
  const [activeSymbol, setActiveSymbol] = useState('AAPL');
  const [timeframe, setTimeframe]   = useState('1D');
  const [chartData, setChartData]   = useState({ bars: [], indicators: {} });
  const [connected, setConnected]   = useState(false);

  const wsRef = useRef(null);
  const reconnRef = useRef(null);

  const connectWS = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({ type: 'subscribe', symbol: 'AAPL', timeframe: '1D' }));
    };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      switch (msg.type) {
        case 'account':   setAccount(msg.data); break;
        case 'positions': setPositions(msg.data); break;
        case 'orders':    setOrders(msg.data); break;
        case 'quotes':    setQuotes(msg.data); break;
        case 'news':      setNews(msg.data); break;
        case 'signals':   setSignals(msg.data); break;
        case 'chart':
          setChartData({ bars: msg.bars, indicators: msg.indicators || {} });
          break;
        case 'target_hit':
          setAlerts(prev => [msg.data, ...prev].slice(0, 8));
          break;
        default: break;
      }
    };

    ws.onclose = () => {
      setConnected(false);
      reconnRef.current = setTimeout(connectWS, 3000);
    };
    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connectWS();
    return () => {
      clearTimeout(reconnRef.current);
      wsRef.current?.close();
    };
  }, [connectWS]);

  const loadChart = useCallback(async (symbol, tf) => {
    try {
      const res = await fetch(`${API}/api/bars/${symbol}?timeframe=${tf}&limit=200`);
      const data = await res.json();
      setChartData(data);
    } catch (e) {
      console.error('Chart load error:', e);
    }
  }, []);

  useEffect(() => {
    loadChart(activeSymbol, timeframe);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'subscribe', symbol: activeSymbol, timeframe }));
    }
  }, [activeSymbol, timeframe, loadChart]);

  const loadTargets = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/targets`);
      setTargets(await res.json());
    } catch {}
  }, []);

  useEffect(() => { loadTargets(); }, [loadTargets]);

  const placeOrder = async (order) => {
    const res = await fetch(`${API}/api/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(order),
    });
    return res.json();
  };

  const sendCommand = async (command) => {
    const res = await fetch(`${API}/api/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command }),
    });
    return res.json();
  };

  const selectSymbol = (symbol) => {
    setActiveSymbol(symbol);
  };

  return (
    <div className="terminal">
      <Header
        account={account}
        connected={connected}
        alerts={alerts}
      />

      <div className="terminal-body">
        {/* LEFT */}
        <div className="left-panel">
          <Watchlist
            quotes={quotes}
            positions={positions}
            activeSymbol={activeSymbol}
            onSelect={selectSymbol}
          />
          <Positions
            positions={positions}
            onSelect={selectSymbol}
          />
          <Orders orders={orders.slice(0, 12)} />
        </div>

        {/* CENTER */}
        <div className="center-panel">
          <Chart
            symbol={activeSymbol}
            data={chartData.bars}
            indicators={chartData.indicators || {}}
            timeframe={timeframe}
            onTimeframeChange={setTimeframe}
            currentQuote={quotes[activeSymbol]}
          />
          <OrderEntry
            symbol={activeSymbol}
            account={account}
            currentQuote={quotes[activeSymbol]}
            onPlaceOrder={placeOrder}
            onCommand={sendCommand}
            onSymbolChange={selectSymbol}
          />
        </div>

        {/* RIGHT */}
        <div className="right-panel">
          <TargetPanel
            targets={targets}
            onRefresh={loadTargets}
            apiBase={API}
            currentQuotes={quotes}
          />
          <Scanner signals={signals} onSelect={selectSymbol} />
          <NewsPanel news={news} onSelect={selectSymbol} />
        </div>
      </div>
    </div>
  );
}
