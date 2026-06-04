import { useState } from 'react';

function timeAgo(iso) {
  if (!iso) return '';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60)   return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

const AGGRESSION_LABELS = ['', 'SAFE', 'CAUTIOUS', 'CAUTIOUS', 'BALANCED',
  'BALANCED', 'ACTIVE', 'ACTIVE', 'AGGRESSIVE', 'AGGRESSIVE', 'YOLO'];
const AGGRESSION_COLORS = ['', '#00bcd4','#00bcd4','#00c853','#00c853',
  '#ffd700','#ffd700','#ff6d00','#ff6d00','#ff1744','#ff1744'];

export default function BotActivity({ botStatus, onToggle, onSelect }) {
  const enabled    = botStatus?.enabled ?? false;
  const activity   = botStatus?.activity ?? [];
  const aggression = botStatus?.aggression ?? 5;
  const [dragging, setDragging] = useState(false);
  const [localAgg, setLocalAgg] = useState(null);

  const displayAgg = localAgg ?? aggression;
  const label = AGGRESSION_LABELS[displayAgg] ?? 'BALANCED';
  const color = AGGRESSION_COLORS[displayAgg] ?? '#ffd700';

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

      {/* Settings summary */}
      <div className="bot-settings-row">
        <span className="dim">Risk {((botStatus?.risk_pct ?? 0.05) * 100).toFixed(0)}%</span>
        <span className="dim">Stop {((botStatus?.stop_pct ?? 0.03) * 100).toFixed(0)}%</span>
        <span className="dim">Target {((botStatus?.target_pct ?? 0.06) * 100).toFixed(0)}%</span>
        <span className="dim">Max {botStatus?.max_positions ?? 5} pos</span>
        <span className="dim">≤${((botStatus?.max_trade_usd ?? 10000)/1000).toFixed(0)}k/trade</span>
      </div>

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
            className={`bot-entry ${entry.action === 'BUY' ? 'buy' : 'sell'}`}
            onClick={() => onSelect(entry.symbol)}
          >
            <div className="bot-entry-top">
              <span className={`bot-action ${entry.action === 'BUY' ? 'green' : 'red'}`}>
                {entry.action}
              </span>
              <span className="bot-sym">{entry.symbol}</span>
              <span className="dim">{entry.qty} sh</span>
              {entry.price && <span className="bot-price">${entry.price.toFixed(2)}</span>}
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
