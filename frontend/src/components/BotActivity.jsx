import { useState } from 'react';

function timeAgo(iso) {
  if (!iso) return '';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60)   return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function fmtK(n) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(1)}k`;
  return `$${n.toFixed(0)}`;
}

const AGGRESSION_LABELS = ['', 'SAFE', 'CAUTIOUS', 'CAUTIOUS', 'BALANCED',
  'BALANCED', 'ACTIVE', 'ACTIVE', 'AGGRESSIVE', 'AGGRESSIVE', 'YOLO'];
const AGGRESSION_COLORS = ['', '#00bcd4','#00bcd4','#00c853','#00c853',
  '#ffd700','#ffd700','#ff6d00','#ff6d00','#ff1744','#ff1744'];

const MODE_LABELS = { long: 'LONG', short: 'SHORT', both: 'LONG+SHORT' };
const MODE_COLORS = { long: '#00e676', short: '#e040fb', both: '#00bcd4' };

function actionColor(action) {
  if (action === 'BUY')   return '#00e676';
  if (action === 'SELL')  return '#ff1744';
  if (action === 'SHORT') return '#e040fb';
  if (action === 'COVER') return '#00bcd4';
  return '#b8c8e0';
}

function entryClass(action) {
  if (action === 'BUY')   return 'buy';
  if (action === 'SELL')  return 'sell';
  if (action === 'SHORT') return 'short';
  if (action === 'COVER') return 'cover';
  return '';
}

export default function BotActivity({ botStatus, account, onToggle, onSelect }) {
  const enabled    = botStatus?.enabled ?? false;
  const activity   = botStatus?.activity ?? [];
  const aggression = botStatus?.aggression ?? 5;
  const mode       = botStatus?.mode ?? 'both';
  const tradeStyle = botStatus?.trade_style ?? 'swing';
  const [dragging, setDragging]     = useState(false);
  const [localAgg, setLocalAgg]     = useState(null);
  const [targetInput, setTargetInput] = useState('');
  const [editingTarget, setEditingTarget] = useState(false);

  const setMode = async (m) => {
    await fetch('/api/bot/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: m }),
    });
  };

  const setStyle = async (s) => {
    await fetch('/api/bot/trade-style', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style: s }),
    });
  };

  const displayAgg = localAgg ?? aggression;
  const label = AGGRESSION_LABELS[displayAgg] ?? 'BALANCED';
  const color = AGGRESSION_COLORS[displayAgg] ?? '#ffd700';

  const portfolioTarget = botStatus?.portfolio_target ?? null;
  const equity = account?.equity ?? account?.portfolio_value ?? 0;
  const progress = portfolioTarget ? Math.min(100, (equity / portfolioTarget) * 100) : null;
  const goalReached = portfolioTarget && equity >= portfolioTarget;

  const onSliderChange = (e) => {
    setLocalAgg(Number(e.target.value));
    setDragging(true);
  };

  const onSliderCommit = async (e) => {
    const val = Number(e.target.value);
    setLocalAgg(val);
    setDragging(false);
    await fetch('/api/bot/aggression', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: val }),
    });
  };

  const submitTarget = async () => {
    const val = parseFloat(targetInput.replace(/[,$k]/gi, v => v.toLowerCase() === 'k' ? '000' : ''));
    if (!isNaN(val) && val > 0) {
      await fetch('/api/bot/portfolio-target', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: val }),
      });
    }
    setEditingTarget(false);
    setTargetInput('');
  };

  const clearTarget = async () => {
    await fetch('/api/bot/portfolio-target', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: null }),
    });
  };

  return (
    <div className="bot-panel">
      {/* Header */}
      <div className="bot-header">
        <div className="bot-title-row">
          <span className="bot-title">AUTO BOT</span>
          <span className={`bot-status-dot ${enabled ? 'active' : 'idle'}`} />
          <span className={`bot-status-text ${enabled ? 'active' : 'idle'}`}>
            {enabled ? 'ACTIVE' : 'PAUSED'}
          </span>
        </div>
        <button className={`bot-toggle ${enabled ? 'on' : 'off'}`} onClick={onToggle}>
          {enabled ? '⏸ PAUSE' : '▶ START'}
        </button>
      </div>

      {/* Aggression slider */}
      <div className="aggression-row">
        <span className="dim" style={{ fontSize: 8, whiteSpace: 'nowrap' }}>AGGRESSION</span>
        <input
          type="range" min="1" max="10" step="1"
          value={displayAgg}
          onChange={onSliderChange}
          onMouseUp={onSliderCommit}
          onTouchEnd={onSliderCommit}
          className="aggression-slider"
          style={{ '--agg-color': color }}
        />
        <span className="aggression-label" style={{ color }}>
          {displayAgg} · {label}
        </span>
      </div>

      {/* Mode toggle */}
      <div className="bot-mode-row">
        <span className="dim" style={{ fontSize: 8, whiteSpace: 'nowrap' }}>MODE</span>
        {['long', 'both', 'short'].map(m => (
          <button
            key={m}
            className={`mode-btn ${mode === m ? 'active' : ''}`}
            style={mode === m ? { color: MODE_COLORS[m], borderColor: MODE_COLORS[m] } : {}}
            onClick={() => setMode(m)}
          >
            {MODE_LABELS[m]}
          </button>
        ))}
      </div>

      {/* Trade style toggle */}
      <div className="bot-mode-row">
        <span className="dim" style={{ fontSize: 8, whiteSpace: 'nowrap' }}>STYLE</span>
        {[
          { key: 'auto',  label: 'AUTO',      color: '#ffd700' },
          { key: 'swing', label: 'SWING',     color: '#00bcd4' },
          { key: 'day',   label: 'DAY TRADE', color: '#ff6d00' },
        ].map(({ key, label, color }) => (
          <button
            key={key}
            className={`mode-btn ${tradeStyle === key ? 'active' : ''}`}
            style={tradeStyle === key ? { color, borderColor: color } : {}}
            onClick={() => setStyle(key)}
          >
            {label}
          </button>
        ))}
        {tradeStyle === 'day' && (
          <span style={{ fontSize: 7, color: '#ff6d00', marginLeft: 'auto' }}>FLAT @3:45PM</span>
        )}
        {tradeStyle === 'auto' && (
          <span style={{ fontSize: 7, color: '#ffd700', marginLeft: 'auto' }}>BOT DECIDES</span>
        )}
      </div>

      {/* Settings summary */}
      <div className="bot-settings-row">
        <span className="dim">Risk {((botStatus?.risk_pct ?? 0.05) * 100).toFixed(0)}%</span>
        <span className="dim">Stop {((botStatus?.stop_pct ?? 0.03) * 100).toFixed(0)}%</span>
        <span className="dim">Target {((botStatus?.target_pct ?? 0.06) * 100).toFixed(0)}%</span>
        <span className="dim">Max {botStatus?.max_positions ?? 5} pos</span>
        <span className="dim">≤${((botStatus?.max_trade_usd ?? 10000)/1000).toFixed(0)}k/trade</span>
      </div>

      {/* Portfolio target */}
      <div className="portfolio-target-row">
        <span className="dim" style={{ fontSize: 8 }}>PORTFOLIO GOAL</span>
        {goalReached && (
          <span className="green" style={{ fontSize: 8, fontWeight: 'bold' }}>✓ GOAL REACHED</span>
        )}
        {portfolioTarget && !goalReached && (
          <span className="dim" style={{ fontSize: 8 }}>
            {fmtK(equity)} → {fmtK(portfolioTarget)}
          </span>
        )}
        {editingTarget ? (
          <div className="target-input-row">
            <input
              className="target-input"
              placeholder="e.g. 100000"
              value={targetInput}
              onChange={e => setTargetInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submitTarget()}
              autoFocus
            />
            <button className="target-btn set" onClick={submitTarget}>SET</button>
            <button className="target-btn cancel" onClick={() => setEditingTarget(false)}>✕</button>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 4 }}>
            <button className="target-btn set" onClick={() => setEditingTarget(true)}>
              {portfolioTarget ? `${fmtK(portfolioTarget)} ✎` : '+ SET GOAL'}
            </button>
            {portfolioTarget && (
              <button className="target-btn cancel" onClick={clearTarget}>✕</button>
            )}
          </div>
        )}
      </div>

      {/* Progress bar */}
      {portfolioTarget && (
        <div className="target-progress-wrap">
          <div
            className="target-progress-bar"
            style={{
              width: `${progress}%`,
              background: goalReached ? '#00e676' : progress > 90 ? '#ffd700' : '#00bcd4',
            }}
          />
          <span className="target-progress-label">{progress.toFixed(1)}%</span>
        </div>
      )}

      {/* Activity feed */}
      <div className="bot-feed">
        {!activity.length && (
          <div className="empty-state">
            {enabled ? 'Scanning market…' : 'Bot is paused — press START'}
          </div>
        )}
        {activity.map((entry, i) => (
          <div
            key={i}
            className={`bot-entry ${entryClass(entry.action)}`}
            onClick={() => onSelect(entry.symbol)}
          >
            <div className="bot-entry-top">
              <span className="bot-action" style={{ color: actionColor(entry.action) }}>
                {entry.action}
              </span>
              <span className="bot-sym">{entry.symbol}</span>
              <span className="dim">{entry.qty} sh</span>
              {entry.price && <span className="bot-price">${entry.price.toFixed(2)}</span>}
              {entry.style && (
                <span style={{ fontSize: 7, color: entry.style === 'day' ? '#ff6d00' : '#00bcd4', fontWeight: 700 }}>
                  {entry.style.toUpperCase()}
                </span>
              )}
              {entry.extended && <span className="gold" style={{ fontSize: 8 }}>EXT</span>}
              <span className="bot-time dim">{timeAgo(entry.time)}</span>
            </div>
            <div className="bot-reason">
              {(entry.reasons ?? [entry.reason]).filter(Boolean).join(' · ')}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
