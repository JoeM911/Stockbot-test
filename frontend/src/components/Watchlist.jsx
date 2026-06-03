import { useState } from 'react';

function pct(positions, symbol) {
  const pos = positions.find(p => p.symbol === symbol);
  return pos ? pos.unrealized_plpc : null;
}

export default function Watchlist({ quotes, positions, activeSymbol, onSelect }) {
  const [newSym, setNewSym] = useState('');

  const symbols = Object.keys(quotes).length
    ? Object.keys(quotes)
    : ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOGL'];

  const addSymbol = async () => {
    const sym = newSym.trim().toUpperCase();
    if (!sym) return;
    try {
      await fetch(`/api/watchlist/${sym}`, { method: 'POST' });
      setNewSym('');
    } catch {}
  };

  return (
    <div className="panel" style={{ flex: '0 0 auto', maxHeight: '35%' }}>
      <div className="panel-header">WATCHLIST</div>
      <div className="panel-content">
        {symbols.map(sym => {
          const q = quotes[sym];
          const change = pct(positions, sym);
          return (
            <div
              key={sym}
              className={`watchlist-row ${activeSymbol === sym ? 'active' : ''}`}
              onClick={() => onSelect(sym)}
            >
              <span className="wl-symbol">{sym}</span>
              <span className="wl-price">
                {q ? `$${q.price.toFixed(2)}` : '--'}
              </span>
              {change != null ? (
                <span className={`wl-chg ${change >= 0 ? 'green' : 'red'}`}>
                  {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                </span>
              ) : <span />}
            </div>
          );
        })}
      </div>
      <div className="wl-add-row">
        <input
          className="t-input sym"
          value={newSym}
          placeholder="ADD…"
          onChange={e => setNewSym(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addSymbol()}
          style={{ flex: 1, width: 'auto' }}
        />
        <button className="btn-neutral" style={{ padding: '2px 8px', fontSize: 9 }} onClick={addSymbol}>+</button>
      </div>
    </div>
  );
}
