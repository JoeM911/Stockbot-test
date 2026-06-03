export default function Scanner({ signals, onSelect }) {
  return (
    <div className="panel" style={{ flex: '1 1 0', minHeight: 80 }}>
      <div className="panel-header">
        <span>MARKET SCANNER</span>
        <span className="dim">{signals.length} signals</span>
      </div>
      <div className="panel-content">
        {!signals.length && <div className="empty-state">Scanning…</div>}
        {signals.map((s, i) => (
          <div key={i} className="scanner-row" onClick={() => onSelect(s.symbol)}>
            <div className="scanner-top">
              <span className="sc-symbol">{s.symbol}</span>
              <span className="sc-price">${s.price?.toFixed(2)}</span>
              <span className={`sc-chg ${s.change_pct >= 0 ? 'green' : 'red'}`}>
                {s.change_pct >= 0 ? '+' : ''}{s.change_pct?.toFixed(2)}%
              </span>
              {s.rsi != null && (
                <span className={`sc-rsi ${s.rsi > 70 ? 'red' : s.rsi < 30 ? 'green' : 'dim'}`}>
                  RSI {s.rsi}
                </span>
              )}
              {s.volume_ratio > 1 && (
                <span className="dim" style={{ fontSize: 8 }}>vol {s.volume_ratio}x</span>
              )}
              <span className={`sc-action ${s.action}`}>{s.action}</span>
            </div>
            <div className="sc-tags">
              {s.signals?.map((sig, j) => (
                <span key={j} className="sc-tag">{sig}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
