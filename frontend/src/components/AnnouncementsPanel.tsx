import React, { useEffect, useState } from 'react';
import { FileText, RefreshCw, ExternalLink } from 'lucide-react';
import { apiService } from '../services/api';
import type { NSEAnnouncement } from '../services/api';

interface Props {
  symbol: string;
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

export const AnnouncementsPanel: React.FC<Props> = ({ symbol }) => {
  const [items, setItems] = useState<NSEAnnouncement[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);

  const clean = symbol.replace('.NS', '');

  useEffect(() => {
    setItems([]);
    setLoading(true);
    apiService.getAnnouncements(clean).then(d => { setItems(d); setLoading(false); });
  }, [clean]);

  const handleRefresh = async () => {
    setRefreshing(true);
    const d = await apiService.refreshAnnouncements(clean);
    setItems(d);
    setRefreshing(false);
  };

  return (
    <div className="w-full flex flex-col">
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-bold text-text-main tracking-wide">NSE Announcements</h3>
          {items.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-surface border border-border-subtle text-text-muted font-mono">{items.length}</span>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          title="Fetch from NSE"
          className="p-1.5 rounded-lg text-text-muted hover:text-text-main hover:bg-bg-surface transition cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto flex flex-col gap-2 max-h-96 pr-1">
        {loading ? (
          <div className="text-xs text-text-muted py-4 text-center animate-pulse">Loading announcements…</div>
        ) : items.length === 0 ? (
          <div className="text-xs text-text-muted py-4 text-center">
            No announcements cached.{' '}
            <button onClick={handleRefresh} className="text-amber-400 hover:underline cursor-pointer">Fetch from NSE</button>
          </div>
        ) : (
          items.map(item => (
            <div
              key={item.id}
              className="rounded-lg border border-border-subtle bg-bg-base/40 hover:bg-bg-base/70 transition p-2.5"
            >
              <div className="flex items-start justify-between gap-2">
                <button
                  className="text-left flex-1 min-w-0 cursor-pointer"
                  onClick={() => setExpanded(expanded === item.id ? null : item.id)}
                >
                  <p className="text-xs font-semibold text-text-main leading-snug line-clamp-2">{item.subject}</p>
                </button>
                <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
                  <span className="text-[10px] text-text-muted font-mono whitespace-nowrap">{timeAgo(item.announcement_date)}</span>
                  {item.file_url && (
                    <a
                      href={item.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-text-muted hover:text-amber-400 transition"
                      title="Open PDF"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>

              {expanded === item.id && item.description && (
                <p className="mt-2 text-[11px] text-text-muted leading-relaxed border-t border-border-subtle pt-2">
                  {item.description.slice(0, 400)}{item.description.length > 400 ? '…' : ''}
                </p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
