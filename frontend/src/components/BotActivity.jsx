function timeAgo(iso) {
  if (!iso) return '';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60)   return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export default function BotActivity({ botStatus, onToggle, onSettings, onSelect }) {
  const enabled  = botStatus?.enabled ?? false;
  const activity = botStatus?.activity ?? [];

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

      {/* Settings row */}
      <div className="bot-settings-row">
        <span className="dim">Risk {((botStatus?.risk_pct ?? 0.05) * 100).toFixed(0)}%</span>
        <span className="dim">Stop {((botStatus?.stop_pct ?? 0.03) * 100).toFixed(0)}%</span>
        <span className="dim">Target {((botStatus?.target_pct ?? 0.06) * 100).toFixed(0)}%</span>
        <span className="dim">Max {botStatus?.max_positions ?? 5} pos</span>
      </div>

      {/* Activity feed */}
      <div className="bot-feed">
        {!activity.length && (
          <div className="empty-state">
            {enabled ? 'Scanning market…' : 'Bot is paused'}
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
