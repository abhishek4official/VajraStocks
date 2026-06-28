import { useEffect, useState } from 'react';
import { ListOrdered, HelpCircle, ChevronDown, ChevronUp, TrendingUp, BarChart2, Zap } from 'lucide-react';
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

const UNIVERSE_FACTORS: Record<string, { label: string; desc: string }> = {
  trend_score:    { label: 'Trend',     desc: 'Price structure — above SMAs, crossover recency, ADX strength' },
  volume_score:   { label: 'Volume',    desc: 'Volume breakout ratio and OBV trend confirmation' },
  rs_score:       { label: 'RS',        desc: 'Relative strength vs NIFTY 50 over 21 trading days' },
  momentum_score: { label: 'Momentum', desc: 'Short-term price returns (1W / 2W / 3W / 4W weighted)' },
  cmf_score:      { label: 'CMF',       desc: 'Chaikin Money Flow — buying pressure and capital flows' },
  breakout_score: { label: 'Breakout',  desc: 'NR7, gap-up, Renko / TLB direction confluence' },
};

const ACADEMIC_FACTORS: Record<string, { label: string; desc: string }> = {
  momentum:       { label: 'Momentum 12-1', desc: '12-month return excluding the most recent month — classic Jegadeesh-Titman momentum factor' },
  low_volatility: { label: 'Low Volatility', desc: 'Negative of 1-year daily return standard deviation — lower vol ranks higher (Ang et al.)' },
  high_proximity: { label: '52wk Proximity', desc: 'How close the price is to its 52-week high — stocks near all-time highs tend to continue (52WH factor)' },
};

function HelpSection({ mode }: { mode: Mode }) {
  const factors = mode === 'universe' ? UNIVERSE_FACTORS : ACADEMIC_FACTORS;

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-surface/40 p-5 space-y-5 text-xs text-text-muted">

      {/* What is this screen */}
      <div>
        <p className="text-text-main font-semibold mb-1 flex items-center gap-1.5">
          <ListOrdered className="w-3.5 h-3.5 text-accent-primary" /> What is Ranking?
        </p>
        <p>
          Ranking cross-sectionally scores every stock in a universe by multiple factors, then combines them into a
          single <span className="text-text-main font-semibold">Composite z-score</span>. The stock with the highest
          composite z ranks #1 — it is the strongest across the most factors simultaneously.
          Use it to find the best setups before scanning for entries.
        </p>
      </div>

      {/* Two modes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className={`rounded-lg border p-3 space-y-1 ${mode === 'universe' ? 'border-accent-primary/40 bg-accent-primary/5' : 'border-border-subtle'}`}>
          <p className="font-semibold text-text-main flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-accent-primary" /> Universe Mode
          </p>
          <p>Ranks all ~2,370 NSE equities using pre-computed snapshot factors (Trend, Volume, RS, Momentum, CMF, Breakout). Updated after every sync. Best for finding top opportunities across the entire market.</p>
        </div>
        <div className={`rounded-lg border p-3 space-y-1 ${mode === 'factors' ? 'border-accent-primary/40 bg-accent-primary/5' : 'border-border-subtle'}`}>
          <p className="font-semibold text-text-main flex items-center gap-1.5">
            <BarChart2 className="w-3.5 h-3.5 text-accent-primary" /> Watchlist Mode
          </p>
          <p>Ranks stocks <span className="text-text-main font-semibold">within your watchlist</span> using academic factors (Momentum 12-1, Low Volatility, 52wk Proximity). Useful for comparing a focused list head-to-head.</p>
        </div>
      </div>

      {/* Column guide */}
      <div>
        <p className="text-text-main font-semibold mb-2 flex items-center gap-1.5">
          <Zap className="w-3.5 h-3.5 text-accent-primary" /> Reading the columns
        </p>
        <div className="space-y-2">
          {[
            { col: '#',           desc: 'Rank by composite z-score. #1 = strongest stock in the universe.' },
            { col: 'Composite z', desc: 'Weighted average of all factor z-scores. The single best summary of a stock\'s overall strength.' },
            { col: 'Pctile',      desc: 'Percentile rank (0–100). 95 means the stock beats 95% of the universe on composite z.' },
            ...Object.entries(factors).map(([, { label, desc }]) => ({ col: label, desc })),
          ].map(({ col, desc }) => (
            <div key={col} className="flex gap-3">
              <span className="shrink-0 w-28 font-mono font-semibold text-text-main">{col}</span>
              <span>{desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Z-score guide */}
      <div>
        <p className="text-text-main font-semibold mb-2">Understanding z-scores</p>
        <p className="mb-2">
          A z-score measures how many <span className="text-text-main font-semibold">standard deviations</span> a stock
          is above or below the universe average for that factor. +1.5 means the stock is in the top ~7% for that factor;
          −1.5 means bottom ~7%.
        </p>
        <div className="flex flex-wrap gap-3">
          {[
            { range: '≥ +2.0', color: 'text-emerald-300', label: 'Exceptional — top 2%' },
            { range: '+1.0 to +2.0', color: 'text-emerald-400', label: 'Strong — top 16%' },
            { range: '−1.0 to +1.0', color: 'text-text-main', label: 'Average range' },
            { range: '−1.0 to −2.0', color: 'text-rose-400', label: 'Weak — bottom 16%' },
            { range: '≤ −2.0', color: 'text-rose-300', label: 'Very weak — bottom 2%' },
          ].map(({ range, color, label }) => (
            <div key={range} className="flex items-center gap-1.5 bg-bg-base/50 rounded-lg px-2.5 py-1.5 border border-border-subtle/50">
              <span className={`font-mono font-bold ${color}`}>{range}</span>
              <span className="text-text-muted">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* How to use */}
      <div>
        <p className="text-text-main font-semibold mb-2">How to use it</p>
        <ol className="space-y-1.5 list-decimal list-inside">
          <li>Run a sync first — Universe mode reads from the latest snapshot.</li>
          <li>Sort by <span className="text-text-main font-semibold">Composite z</span> (already sorted). Stocks in the top 20 have the broadest factor leadership.</li>
          <li>Look for stocks with <span className="text-emerald-400 font-semibold">green</span> across most individual factors — that means the strength is not coming from just one signal.</li>
          <li>A high RS z + high Momentum z = price leadership relative to the market. Add Trend z ≥ +1 and you have a textbook Stage 2 candidate.</li>
          <li>Use <span className="text-text-main font-semibold">Watchlist mode</span> to compare stocks you're already watching — it tells you which ones to prioritise for entry.</li>
          <li>Avoid stocks with a strong Momentum z but weak or negative Trend z — the move may be extended or unconfirmed by structure.</li>
        </ol>
      </div>
    </div>
  );
}

export function RankingPanel() {
  const [mode, setMode] = useState<Mode>('universe');
  const [rows, setRows] = useState<RankRow[]>([]);
  const [factors, setFactors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);

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

  const factorMeta = mode === 'universe' ? UNIVERSE_FACTORS : ACADEMIC_FACTORS;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ListOrdered className="w-5 h-5 text-accent-primary" />
          <h2 className="text-lg font-bold text-text-main">Ranking</h2>
          <span className="text-[11px] text-text-muted">Relative strength — z-scored factors, weighted composite</span>
        </div>
        <button
          onClick={() => setShowHelp(h => !h)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium transition cursor-pointer ${
            showHelp
              ? 'bg-accent-primary/10 border-accent-primary/40 text-accent-primary'
              : 'border-border-subtle text-text-muted hover:text-text-main'
          }`}
          title="How to use Ranking"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          How to use
          {showHelp ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>

      {/* Collapsible help */}
      {showHelp && <HelpSection mode={mode} />}

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
                <th className="text-right px-3 py-2" title="Weighted average of all factor z-scores">Composite z</th>
                <th className="text-right px-3 py-2" title="Percentile rank in universe (0–100)">Pctile</th>
                {factors.map(f => (
                  <th key={f} className="text-right px-3 py-2" title={factorMeta[f]?.desc}>
                    {factorMeta[f]?.label ?? f.replace(/_/g, ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.symbol} className="border-b border-border-subtle/50 hover:bg-bg-surface/40 transition-colors">
                  <td className="px-3 py-1.5 text-right text-text-muted">{i + 1}</td>
                  <td className="px-3 py-1.5 font-semibold">{r.symbol.replace('.NS', '')}</td>
                  <td className={`px-3 py-1.5 text-right font-semibold ${zColor(r.composite_z)}`}>{Z(r.composite_z)}</td>
                  <td className="px-3 py-1.5 text-right text-text-muted">{r.percentile === null ? '—' : r.percentile.toFixed(0)}</td>
                  {factors.map(f => (
                    <td key={f} className={`px-3 py-1.5 text-right ${zColor(r.factors[f])}`}>{Z(r.factors[f])}</td>
                  ))}
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
