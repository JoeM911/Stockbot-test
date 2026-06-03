import { useState } from 'react';

export default function TargetPanel({ targets, onRefresh, apiBase, currentQuotes }) {
  const [sym, setSym]     = useState('');
  const [price, setPrice] = useState('');
  const [dir, setDir]     = useState('above');
  const [note, setNote]   = useState('');
  const [saving, setSaving] = useState(false);

  const add = async () => {
    if (!sym || !price) return;
    setSaving(true);
    try {
      await fetch(`${apiBase}/api/targets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: sym.toUpperCase(),
          target_price: Number(price),
          target_type: dir,
          note,
        }),
      });
      setSym(''); setPrice(''); setNote('');
      onRefresh();
    } catch {}
    setSaving(false);
  };

  const remove = async (id) => {
    await fetch(`${apiBase}/api/targets/${id}`, { method: 'DELETE' });
    onRefresh();
  };

  return (
    <div className="panel" style={{ flex: '0 0 auto', maxHeight: '32%' }}>
      <div className="panel-header">
        <span>PRICE TARGETS</span>
        <span className="dim">{targets.length}</span>
      </div>

      <div className="target-add">
        <input
          className="t-input sym"
          value={sym}
          onChange={e => setSym(e.target.value)}
          placeholder="SYM"
          style={{ width: 56 }}
        />
        <input
          className="t-input price"
          value={price}
          onChange={e => setPrice(e.target.value)}
          placeholder="$"
          type="number"
          style={{ width: 64 }}
        />
        <select className="t-select" value={dir} onChange={e => setDir(e.target.value)} style={{ fontSize: 9 }}>
          <option value="above">ABOVE</option>
          <option value="below">BELOW</option>
        </select>
        <input
          className="t-input"
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="note…"
          style={{ flex: 1, minWidth: 0 }}
        />
        <button className="btn-neutral" style={{ padding: '2px 8px', fontSize: 9 }} onClick={add} disabled={saving}>
          SET
        </button>
      </div>

      <div className="panel-content">
        {!targets.length && <div className="empty-state">No targets set</div>}
        {targets.map(t => {
          const current = currentQuotes?.[t.symbol]?.price;
          const diff = current ? ((current - t.target_price) / t.target_price * 100) : null;
          const near = diff != null && Math.abs(diff) < 3;
          return (
            <div key={t.id} className="target-row" style={near ? { background: '#ffd70008' } : {}}>
              <span className={`tgt-symbol ${near ? 'gold' : ''}`}>{t.symbol}</span>
              <span className="tgt-price">
                {t.target_type === 'above' ? '▲' : '▼'} ${t.target_price.toFixed(2)}
              </span>
              <div style={{ overflow: 'hidden' }}>
                <div className="tgt-note">{t.note || '--'}</div>
                {current != null && (
                  <div style={{ fontSize: 8 }} className={diff != null && ((t.target_type === 'above' && diff > 0) || (t.target_type === 'below' && diff < 0)) ? 'green' : 'dim'}>
                    Now ${current.toFixed(2)} · {diff != null ? `${diff >= 0 ? '+' : ''}${diff.toFixed(1)}%` : ''}
                  </div>
                )}
              </div>
              <button className="btn-icon" onClick={() => remove(t.id)} title="Remove">×</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
