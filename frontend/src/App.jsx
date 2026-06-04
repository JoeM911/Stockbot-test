import { useState, useEffect, useRef, useCallback } from 'react';
import Login from './components/Login';
import Header from './components/Header';
import Chart from './components/Chart';
import Positions from './components/Positions';
import Orders from './components/Orders';
import NewsPanel from './components/NewsPanel';
import BotActivity from './components/BotActivity';
import GrowthChart from './components/GrowthChart';
import SentimentPanel from './components/SentimentPanel';
import Scanner from './components/Scanner';
import Watchlist from './components/Watchlist';

const API = '';
const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`;

export default function App() {
  const [authed, setAuthed] = useState(false);

  // Check if already authenticated (cookie set) by hitting a protected endpoint
  useEffect(() => {
    fetch('/api/demo-mode')
      .then(r => { if (r.ok) setAuthed(true); })
      .catch(() => {});
  }, []);

  if (!authed) {
    return <Login onAuth={() => setAuthed(true)} />;
  }

  return <Dashboard />;
}

function Dashboard() {
  const [account, setAccount]       = useState(null);
  const [positions, setPositions]   = useState([]);
  const [orders, setOrders]         = useState([]);
  const [quotes, setQuotes]         = useState({});
  const [news, setNews]             = useState([]);
  const [signals, setSignals]       = useState([]);
  const [targets, setTargets]       = useState([]);
  const [alerts, setAlerts]         = useState([]);
  const [botStatus, setBotStatus]   = useState(null);
  const [sentiment, setSentiment]   = useState(null);
  const [activeSymbol, setActiveSymbol] = useState('AAPL');
  const [timeframe, setTimeframe]   = useState('1D');
  const [chartData, setChartData]   = useState({ bars: [], indicators: {} });
  const [connected, setConnected]   = useState(false);

  const wsRef    = useRef(null);
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
        case 'account':      setAccount(msg.data); break;
        case 'positions':    setPositions(msg.data); break;
        case 'orders':       setOrders(msg.data); break;
        case 'quotes':       setQuotes(msg.data); break;
        case 'news':         setNews(msg.data); break;
        case 'signals':      setSignals(msg.data); break;
        case 'bot_status':   setBotStatus(msg.data); break;
        case 'sentiment':    setSentiment(msg.data); break;
        case 'bot_activity':
          setBotStatus(prev => prev ? {
            ...prev,
            activity: [msg.data, ...(prev.activity ?? [])].slice(0, 100),
          } : prev);
          break;
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
    return () => { clearTimeout(reconnRef.current); wsRef.current?.close(); };
  }, [connectWS]);

  // Load bot status on mount
  useEffect(() => {
    fetch(`${API}/api/bot/status`).then(r => r.json()).then(setBotStatus).catch(() => {});
  }, []);

  const loadChart = useCallback(async (symbol, tf) => {
    try {
      const res = await fetch(`${API}/api/bars/${symbol}?timeframe=${tf}&limit=200`);
      setChartData(await res.json());
    } catch {}
  }, []);

  useEffect(() => {
    loadChart(activeSymbol, timeframe);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'subscribe', symbol: activeSymbol, timeframe }));
    }
  }, [activeSymbol, timeframe, loadChart]);

  const loadTargets = useCallback(async () => {
    try { setTargets(await (await fetch(`${API}/api/targets`)).json()); } catch {}
  }, []);
  useEffect(() => { loadTargets(); }, [loadTargets]);

  const toggleBot = async () => {
    const res = await fetch(`${API}/api/bot/toggle`, { method: 'POST' });
    setBotStatus(await res.json().catch(() => ({})));
    // Refresh full status
    fetch(`${API}/api/bot/status`).then(r => r.json()).then(setBotStatus).catch(() => {});
  };

  return (
    <div className="terminal">
      <Header account={account} connected={connected} alerts={alerts} botEnabled={botStatus?.enabled} />

      <div className="terminal-body">
        {/* LEFT */}
        <div className="left-panel">
          <Watchlist
            quotes={quotes}
            positions={positions}
            activeSymbol={activeSymbol}
            onSelect={setActiveSymbol}
          />
          <Positions positions={positions} onSelect={setActiveSymbol} />
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
          <BotActivity
            botStatus={botStatus}
            account={account}
            onToggle={toggleBot}
            onSelect={setActiveSymbol}
          />
        </div>

        {/* RIGHT */}
        <div className="right-panel">
          <GrowthChart />
          <SentimentPanel sentiment={sentiment} onSelect={setActiveSymbol} />
          <Scanner signals={signals} onSelect={setActiveSymbol} />
          <NewsPanel news={news} onSelect={setActiveSymbol} />
        </div>
      </div>
    </div>
  );
}
