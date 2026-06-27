import { useEffect, useState } from 'react';
import { ListOrdered } from 'lucide-react';
import { apiService, type RankRow } from '../services/api';

const Z = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2);

function zColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return 'text-text-muted';
  if (v >= 1) return 'text-emerald-400';
  if (v <= -1) return 'text-rose-400';
  return 'text-text-main';
}

type Mode = 'universe' | 'factors';
type Watchlist = { id: string; name: string; items: { symbol: string }[] };

export function RankingPanel() {
  const [mode, setMode] = useState<Mode>('universe');
  const [rows, setRows] = useState<RankRow[]>([]);
  const [factors, setFactors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Factor-mode state
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [wlId, setWlId] = useState<string>('');

  // Universe mode loads on mount / when switching to it.
  useEffect(() => {
    if (mode !== 'universe') return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [r, f] = await Promise.all([apiService.getRanking(200), apiService.getRankingFactors()]);
        if (!cancelled) { setRows(r); setFactors(f.factors); }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load ranking');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [mode]);

  // Factor mode: load watchlists once when entered.
  useEffect(() => {
    if (mode !== 'factors' || watchlists.length) return;
    apiService.fetchWatchlists().then(setWatchlists).catch(() => setWatchlists([]));
  }, [mode, watchlists.length]);

  const rankWatchlist = async (id: string) => {
    setWlId(id);
    const wl = watchlists.find(w => w.id === id);
    if (!wl) return;
    setLoading(true);
    setError(null);
    try {
      const r = await apiService.rankByFactors(wl.items.map(i => i.symbol));
      setRows(r);
      setFactors(['momentum', 'low_volatility', 'high_proximity']);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to rank');
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4">
      <div className="flex items-center gap-2">
        <ListOrdered className="w-5 h-5 text-accent-primary" />
        <h2 className="text-lg font-bold text-text-main">Ranking</h2>
        <span className="text-[11px] text-text-muted">Relative strength — z-scored factors, weighted composite</span>
      </div>

      {/* Mode toggle */}
      <div className="flex items-center gap-2">
        {([['universe', 'Universe (snapshot factors)'], ['factors', 'Watchlist (academic factors)']] as const).map(([m, label]) => (
          <button
            key={m}
            onClick={() => { setMode(m); setRows([]); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition cursor-pointer ${
              mode === m ? 'bg-accent-primary text-accent-text border-transparent' : 'border-border-subtle text-text-muted hover:text-text-main'
            }`}
          >
            {label}
          </button>
        ))}
        {mode === 'factors' && (
          <select
            value={wlId}
            onChange={e => rankWatchlist(e.target.value)}
            className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-xs text-text-main"
          >
            <option value="">Select a watchlist…</option>
            {watchlists.map(w => <option key={w.id} value={w.id}>{w.name} ({w.items.length})</option>)}
          </select>
        )}
      </div>

      {loading && <p className="text-sm text-text-muted">Computing…</p>}
      {error && <p className="text-sm text-rose-400">{error}</p>}

      {!loading && rows.length > 0 && (
        <div className="rounded-xl border border-border-subtle bg-bg-surface/60 overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-text-muted border-b border-border-subtle">
              <tr>
                <th className="text-right px-3 py-2">#</th>
                <th className="text-left px-3 py-2">Symbol</th>
                <th className="text-right px-3 py-2">Composite z</th>
                <th className="text-right px-3 py-2">Pctile</th>
                {factors.map(f => <th key={f} className="text-right px-3 py-2 capitalize">{f.replace('_', ' ')}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.symbol} className="border-b border-border-subtle/50">
                  <td className="px-3 py-1.5 text-right text-text-muted">{i + 1}</td>
                  <td className="px-3 py-1.5 font-semibold">{r.symbol.replace('.NS', '')}</td>
                  <td className={`px-3 py-1.5 text-right font-semibold ${zColor(r.composite_z)}`}>{Z(r.composite_z)}</td>
                  <td className="px-3 py-1.5 text-right text-text-muted">{r.percentile === null ? '—' : r.percentile.toFixed(0)}</td>
                  {factors.map(f => <td key={f} className={`px-3 py-1.5 text-right ${zColor(r.factors[f])}`}>{Z(r.factors[f])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && rows.length === 0 && !error && (
        <p className="text-xs text-text-muted">
          {mode === 'factors' ? 'Pick a watchlist to rank its symbols by momentum / low-volatility / 52wk-high.' : 'No ranked symbols — run a sync first.'}
        </p>
      )}
    </div>
  );
}
