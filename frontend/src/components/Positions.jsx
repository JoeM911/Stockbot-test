function fmt(n, d = 2) {
  if (n == null) return '--';
  return Number(n).toFixed(d);
}

export default function Positions({ positions, onSelect }) {
  if (!positions.length) {
    return (
      <div className="panel" style={{ flex: '0 0 auto' }}>
        <div className="panel-header">POSITIONS</div>
        <div className="empty-state">No open positions</div>
      </div>
    );
  }

  return (
    <div className="panel" style={{ flex: '1 1 0', minHeight: 80 }}>
      <div className="panel-header">
        <span>POSITIONS</span>
        <span className="dim">{positions.length}</span>
      </div>
      <div className="panel-content">
        <table className="pos-table">
          <thead>
            <tr>
              <th>SYM</th>
              <th>QTY</th>
              <th>P&amp;L%</th>
            </tr>
          </thead>
          <tbody>
            {positions.map(p => (
              <tr key={p.symbol} onClick={() => onSelect(p.symbol)} title={`Avg: $${fmt(p.avg_entry_price)} | Curr: $${fmt(p.current_price)} | P&L: $${fmt(p.unrealized_pl)}`}>
                <td style={{ fontWeight: 700 }}>{p.symbol}</td>
                <td>{fmt(p.qty, 0)}</td>
                <td className={p.unrealized_plpc >= 0 ? 'green' : 'red'}>
                  {p.unrealized_plpc >= 0 ? '+' : ''}{fmt(p.unrealized_plpc)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Position detail cards */}
        {positions.map(p => (
          <div
            key={`d-${p.symbol}`}
            style={{ padding: '4px 8px', borderBottom: '1px solid #0a1020', fontSize: 9 }}
            onClick={() => onSelect(p.symbol)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="dim">Entry</span>
              <span>${fmt(p.avg_entry_price)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="dim">Current</span>
              <span>${fmt(p.current_price)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="dim">Value</span>
              <span>${fmt(p.market_value)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="dim">P&amp;L</span>
              <span className={p.unrealized_pl >= 0 ? 'green' : 'red'}>
                {p.unrealized_pl >= 0 ? '+' : ''}${fmt(p.unrealized_pl)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
