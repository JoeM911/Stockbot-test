export default function SentimentPanel({ sentiment, onSelect }) {
  const scores   = sentiment?.scores   ?? [];
  const trending = sentiment?.trending ?? [];
  const reddit   = sentiment?.reddit   ?? [];
  const loaded   = sentiment !== null;

  return (
    <div className="panel" style={{ flex: '1 1 0', minHeight: 80 }}>
      <div className="panel-header">
        <span>SOCIAL SENTIMENT</span>
        <span className="dim" style={{ fontSize: 8 }}>StockTwits · WSB</span>
      </div>
      <div className="panel-content">

        {!loaded && <div className="empty-state">Loading sentiment…</div>}

        {/* StockTwits sentiment bars */}
        {loaded && scores.length === 0 && trending.length === 0 && (
          <div className="empty-state dim" style={{ fontSize: 8 }}>
            StockTwits unavailable
          </div>
        )}

        {scores.slice(0, 8).map((s) => (
          <div key={s.symbol} className="sent-row" onClick={() => onSelect(s.symbol)}>
            <span className="sent-sym">{s.symbol}</span>
            <div className="sent-bars">
              <div className="sent-bull" style={{ width: `${s.bullish_pct}%` }} />
              <div className="sent-bear" style={{ width: `${s.bearish_pct}%` }} />
            </div>
            <span className="green" style={{ fontSize: 9, minWidth: 28, textAlign: 'right' }}>
              {s.bullish_pct}%
            </span>
          </div>
        ))}

        {/* Reddit WSB — shown independently */}
        {loaded && reddit.length > 0 && (
          <>
            <div className="sent-section-header">REDDIT WSB MENTIONS</div>
            {reddit.slice(0, 6).map((r) => (
              <div key={r.symbol} className="sent-reddit-row" onClick={() => onSelect(r.symbol)}>
                <span className="sent-sym">{r.symbol}</span>
                <div className="sent-mention-bar-wrap">
                  <div
                    className="sent-mention-bar"
                    style={{ width: `${Math.min(100, (r.mentions / (reddit[0]?.mentions || 1)) * 100)}%` }}
                  />
                </div>
                <span className="gold" style={{ fontSize: 9 }}>{r.mentions}</span>
              </div>
            ))}
          </>
        )}

        {loaded && reddit.length === 0 && scores.length === 0 && (
          <div className="empty-state dim" style={{ fontSize: 8 }}>
            Reddit WSB unavailable
          </div>
        )}

        {/* Trending pills */}
        {trending.length > 0 && (
          <>
            <div className="sent-section-header">TRENDING ON STOCKTWITS</div>
            <div className="sent-trending-wrap">
              {trending.slice(0, 12).map((t) => (
                <span
                  key={t.symbol}
                  className="sent-trending-pill"
                  onClick={() => onSelect(t.symbol)}
                >{t.symbol}</span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
