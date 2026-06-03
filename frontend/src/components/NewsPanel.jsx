function timeAgo(isoStr) {
  if (!isoStr) return '';
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60)   return `${Math.floor(diff)}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

export default function NewsPanel({ news, onSelect }) {
  return (
    <div className="panel" style={{ flex: '1 1 0', minHeight: 80 }}>
      <div className="panel-header">
        <span>MARKET NEWS</span>
        <span className="dim">{news.length}</span>
      </div>
      <div className="panel-content">
        {!news.length && <div className="empty-state">Loading news…</div>}
        {news.map((article, i) => (
          <div
            key={article.id || i}
            className="news-item"
            onClick={() => article.symbols?.[0] && onSelect(article.symbols[0])}
          >
            <div className="news-headline">{article.headline}</div>
            <div className="news-meta">
              <span className="news-source">{article.source}</span>
              <span className={`sent-${article.sentiment}`}>
                {article.sentiment === 'positive' ? '▲' : article.sentiment === 'negative' ? '▼' : '●'}
              </span>
              {article.symbols?.length > 0 && (
                <span className="news-syms">{article.symbols.slice(0, 3).join(' ')}</span>
              )}
              <span className="news-time">{timeAgo(article.created_at)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
