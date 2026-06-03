function timeAgo(isoStr) {
  if (!isoStr) return '';
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60)  return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function statusClass(status) {
  if (status === 'filled')   return 'status-filled';
  if (status === 'canceled' || status === 'cancelled') return 'status-canceled';
  if (status === 'rejected') return 'status-rejected';
  return 'status-pending';
}

export default function Orders({ orders }) {
  return (
    <div className="panel" style={{ flex: '0 0 auto', maxHeight: '30%' }}>
      <div className="panel-header">
        <span>RECENT ORDERS</span>
        <span className="dim">{orders.length}</span>
      </div>
      <div className="panel-content">
        {!orders.length && <div className="empty-state">No recent orders</div>}
        {orders.map(o => (
          <div key={o.id} className="order-row">
            <span className={o.side === 'buy' ? 'green bold' : 'red bold'}>
              {o.side.toUpperCase()}
            </span>
            <span className="order-sym">{o.symbol}</span>
            <span className="dim">{o.filled_qty > 0 ? o.filled_qty : o.qty}</span>
            <span className={statusClass(o.status)}>{o.status}</span>
            {o.filled_avg_price && (
              <span className="gold" style={{ fontSize: 9 }}>${Number(o.filled_avg_price).toFixed(2)}</span>
            )}
            <span className="dim" style={{ fontSize: 8 }}>{timeAgo(o.submitted_at)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
