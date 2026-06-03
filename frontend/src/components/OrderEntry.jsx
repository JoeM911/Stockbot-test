import { useState, useEffect } from 'react';

const COMMANDS_HELP = 'BUY AAPL 10 | SELL TSLA 5 | TARGET AAPL 200 above | ADD NVDA | REMOVE NVDA | CLOSE AAPL';

export default function OrderEntry({ symbol, account, currentQuote, onPlaceOrder, onCommand, onSymbolChange }) {
  const [sym, setSym]         = useState(symbol);
  const [qty, setQty]         = useState('');
  const [orderType, setOrderType] = useState('market');
  const [limitPrice, setLimit] = useState('');
  const [stopPrice, setStop]  = useState('');
  const [tif, setTif]         = useState('day');
  const [feedback, setFeedback] = useState('');
  const [isError, setIsError]  = useState(false);
  const [cmdInput, setCmdInput] = useState('');
  const [loading, setLoading]  = useState(false);

  useEffect(() => { setSym(symbol); }, [symbol]);

  const price = currentQuote?.price;

  const handleOrder = async (side) => {
    if (!sym || !qty || isNaN(qty) || Number(qty) <= 0) {
      setIsError(true);
      setFeedback('Enter a valid symbol and quantity');
      return;
    }
    setLoading(true);
    try {
      const result = await onPlaceOrder({
        symbol: sym.toUpperCase(),
        qty: Number(qty),
        side,
        type: orderType,
        limit_price: limitPrice ? Number(limitPrice) : null,
        stop_price: stopPrice ? Number(stopPrice) : null,
        time_in_force: tif,
      });
      if (result.error) {
        setIsError(true);
        setFeedback(result.error);
      } else {
        setIsError(false);
        setFeedback(`✓ ${side.toUpperCase()} ${qty} ${sym.toUpperCase()} submitted (${result.status})`);
        setQty('');
      }
    } catch (e) {
      setIsError(true);
      setFeedback(String(e));
    }
    setLoading(false);
  };

  const handleCommand = async (e) => {
    if (e.key !== 'Enter' || !cmdInput.trim()) return;
    const cmd = cmdInput.trim();
    setCmdInput('');
    setLoading(true);

    // Local parse for symbol switching
    const parts = cmd.toUpperCase().split(/\s+/);
    if (parts[0] === 'CHART' && parts[1]) {
      onSymbolChange(parts[1]);
      setFeedback(`Chart: ${parts[1]}`);
      setIsError(false);
      setLoading(false);
      return;
    }

    try {
      const result = await onCommand(cmd);
      if (result.error) {
        setIsError(true);
        setFeedback(result.error);
      } else {
        setIsError(false);
        setFeedback(result.message || '✓ Done');
      }
    } catch (e) {
      setIsError(true);
      setFeedback(String(e));
    }
    setLoading(false);
  };

  const estCost = qty && price ? (Number(qty) * price).toFixed(2) : null;

  return (
    <div className="order-entry-panel">
      {/* Order form */}
      <div className="order-form">
        <span className="order-form-label">ORDER</span>

        <input
          className="t-input sym"
          value={sym}
          onChange={e => { setSym(e.target.value); onSymbolChange(e.target.value.toUpperCase()); }}
          placeholder="SYM"
          onBlur={e => e.target.value && onSymbolChange(e.target.value.toUpperCase())}
        />

        <input
          className="t-input qty"
          value={qty}
          onChange={e => setQty(e.target.value)}
          placeholder="QTY"
          type="number"
          min="0"
        />

        <select className="t-select" value={orderType} onChange={e => setOrderType(e.target.value)}>
          <option value="market">MARKET</option>
          <option value="limit">LIMIT</option>
          <option value="stop">STOP</option>
          <option value="stop_limit">STOP-LMT</option>
        </select>

        {(orderType === 'limit' || orderType === 'stop_limit') && (
          <input className="t-input price" value={limitPrice} onChange={e => setLimit(e.target.value)} placeholder="LMT $" type="number" />
        )}
        {(orderType === 'stop' || orderType === 'stop_limit') && (
          <input className="t-input price" value={stopPrice} onChange={e => setStop(e.target.value)} placeholder="STOP $" type="number" />
        )}

        <select className="t-select" value={tif} onChange={e => setTif(e.target.value)}>
          <option value="day">DAY</option>
          <option value="gtc">GTC</option>
        </select>

        {price != null && (
          <span className="dim" style={{ fontSize: 9, whiteSpace: 'nowrap' }}>
            ${price.toFixed(2)}{estCost ? ` · ~$${estCost}` : ''}
          </span>
        )}

        <button className="btn-buy"  onClick={() => handleOrder('buy')}  disabled={loading}>BUY</button>
        <button className="btn-sell" onClick={() => handleOrder('sell')} disabled={loading}>SELL</button>
      </div>

      {/* Bloomberg command line */}
      <div className="command-row">
        <span className="cmd-prompt">&gt;</span>
        <input
          className="cmd-input"
          value={cmdInput}
          onChange={e => setCmdInput(e.target.value)}
          onKeyDown={handleCommand}
          placeholder={COMMANDS_HELP}
        />
      </div>

      {feedback && (
        <div className={`cmd-feedback ${isError ? 'cmd-err' : 'cmd-ok'}`}>{feedback}</div>
      )}
    </div>
  );
}
