import React, { useEffect, useState } from 'react';
import { Newspaper, RefreshCw, ExternalLink } from 'lucide-react';
import { apiService } from '../services/api';
import type { NewsItem } from '../services/api';

interface Props {
  symbol: string;
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (hours < 1) return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

export const NewsPanel: React.FC<Props> = ({ symbol }) => {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const clean = symbol.replace('.NS', '');

  useEffect(() => {
    setItems([]);
    setLoading(true);
    apiService.getNews(clean).then(d => { setItems(d); setLoading(false); });
  }, [clean]);

  const handleRefresh = async () => {
    setRefreshing(true);
    const d = await apiService.refreshNews(clean);
    setItems(d);
    setRefreshing(false);
  };

  return (
    <div className="w-full flex flex-col">
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div className="flex items-center gap-2">
          <Newspaper className="w-4 h-4 text-sky-400" />
          <h3 className="text-sm font-bold text-white tracking-wide">News</h3>
          {items.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">{items.length}</span>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          title="Refresh news"
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto flex flex-col gap-2 max-h-96 pr-1">
        {loading ? (
          <div className="text-xs text-slate-500 py-4 text-center animate-pulse">Loading news…</div>
        ) : items.length === 0 ? (
          <div className="text-xs text-slate-500 py-4 text-center">
            No news cached.{' '}
            <button onClick={handleRefresh} className="text-sky-400 hover:underline cursor-pointer">Fetch now</button>
          </div>
        ) : (
          items.map(item => (
            <a
              key={item.id}
              href={item.link ?? '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-2.5 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-900/70 hover:border-slate-700 transition p-2.5 group"
            >
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-slate-200 group-hover:text-sky-300 transition leading-snug line-clamp-2">
                  {item.title}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  {item.publisher && (
                    <span className="text-[10px] text-slate-500 font-medium truncate max-w-[120px]">{item.publisher}</span>
                  )}
                  <span className="text-[10px] text-slate-600 font-mono">{timeAgo(item.published_at)}</span>
                </div>
              </div>
              {item.link && (
                <ExternalLink className="w-3 h-3 text-slate-600 group-hover:text-sky-400 transition mt-0.5 shrink-0" />
              )}
            </a>
          ))
        )}
      </div>
    </div>
  );
};
