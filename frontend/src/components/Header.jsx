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
      const now = new Date();
      const day = now.getUTCDay();
      const mins = now.getUTCHours() * 60 + now.getUTCMinutes();
      // Market open 14:30-21:00 UTC Mon-Fri
      const open = day >= 1 && day <= 5 && mins >= 870 && mins < 1260;
      setStatus(open ? 'OPEN' : 'CLOSED');
    };
    check();
    const id = setInterval(check, 30000);
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

        <span className={`market-badge ${marketStatus === 'OPEN' ? 'open' : 'closed'}`}>
          {marketStatus}
        </span>

        <span className="clock">{clock}</span>

        <div className={`conn-dot ${connected ? 'on' : 'off'}`} title={connected ? 'Live' : 'Disconnected'} />
      </div>
    </div>
  );
}
