import { useState, useEffect } from 'react';

function fmt(n, decimals = 2) {
  if (n == null) return '--';
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtMoney(n) {
  if (n == null) return '--';
  const abs = Math.abs(n);
  const prefix = n < 0 ? '-$' : '$';
  return prefix + abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function useMarketStatus() {
  const [status, setStatus] = useState('--');
  useEffect(() => {
    const check = () => {
      // Convert to ET
      const etStr = new Date().toLocaleString('en-US', { timeZone: 'America/New_York' });
      const et = new Date(etStr);
      const day  = et.getDay();   // 0=Sun,6=Sat
      const mins = et.getHours() * 60 + et.getMinutes();
      if (day === 0 || day === 6) { setStatus('CLOSED'); return; }
      if (mins >= 4*60  && mins < 9*60+30)  { setStatus('PRE-MKT');   return; }
      if (mins >= 9*60+30 && mins < 16*60)  { setStatus('OPEN');      return; }
      if (mins >= 16*60 && mins < 20*60)    { setStatus('AFTER-HRS'); return; }
      setStatus('CLOSED');
    };
    check();
    const id = setInterval(check, 15000);
    return () => clearInterval(id);
  }, []);
  return status;
}

function useClock() {
  const [time, setTime] = useState('');
  useEffect(() => {
    const update = () => setTime(new Date().toLocaleTimeString('en-US', { hour12: false, timeZone: 'America/New_York' }) + ' ET');
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

export default function Header({ account, connected, alerts, botEnabled }) {
  const marketStatus = useMarketStatus();
  const clock = useClock();
  const tradingMode = (import.meta.env.VITE_TRADING_MODE || 'manual').toLowerCase();

  const pnl = account?.pnl ?? 0;
  const pnlPct = account?.pnl_pct ?? 0;

  return (
    <div className="terminal-header">
      <div>
        <div className="brand">STOCKBOT</div>
        <div className="brand-sub">TERMINAL</div>
      </div>

      {account && (
        <div className="account-strip">
          <div className="acc-item">
            <span className="acc-label">EQUITY</span>
            <span className="acc-value">{fmtMoney(account.equity)}</span>
          </div>
          <div className="acc-item">
            <span className="acc-label">BUYING PWR</span>
            <span className="acc-value">{fmtMoney(account.buying_power)}</span>
          </div>
          <div className="acc-item">
            <span className="acc-label">DAY P&L</span>
            <span className={`acc-value ${pnl >= 0 ? 'green' : 'red'}`}>
              {pnl >= 0 ? '+' : ''}{fmtMoney(pnl)}
              <span style={{ fontSize: 9, marginLeft: 4 }}>
                ({pnl >= 0 ? '+' : ''}{fmt(pnlPct)}%)
              </span>
            </span>
          </div>
          <div className="acc-item">
            <span className="acc-label">PORTFOLIO</span>
            <span className="acc-value">{fmtMoney(account.portfolio_value)}</span>
          </div>
          <div className="acc-item">
            <span className="acc-label">DT TRADES</span>
            <span className={`acc-value ${account.day_trade_count >= 3 ? 'red' : 'gold'}`}>
              {account.day_trade_count}/3
            </span>
          </div>
        </div>
      )}

      <div className="header-right">
        {alerts.length > 0 && (
          <div className="alert-strip">
            {alerts.slice(0, 3).map((a, i) => (
              <div key={i} className="alert-pill">
                🎯 {a.symbol} ${a.target_price}
              </div>
            ))}
          </div>
        )}

        {botEnabled != null && (
          <span className={`mode-badge ${botEnabled ? 'mode-all' : 'mode-manual'}`}>
            BOT {botEnabled ? 'ON' : 'OFF'}
          </span>
        )}

        <span className={`market-badge ${
          marketStatus === 'OPEN' ? 'open' :
          marketStatus === 'PRE-MKT' || marketStatus === 'AFTER-HRS' ? 'extended' : 'closed'
        }`}>
          {marketStatus}
        </span>

        <span className="clock">{clock}</span>

        <div className={`conn-dot ${connected ? 'on' : 'off'}`} title={connected ? 'Live' : 'Disconnected'} />
      </div>
    </div>
  );
}
