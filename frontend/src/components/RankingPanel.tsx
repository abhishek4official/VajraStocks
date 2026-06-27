import { useEffect, useState } from 'react';
import { ArrowUpDown, ListOrdered } from 'lucide-react';
import { apiService, type RankRow } from '../services/api';

const Z = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2);

function zColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return 'text-text-muted';
  if (v >= 1) return 'text-emerald-400';
  if (v <= -1) return 'text-rose-400';
  return 'text-text-main';
}

export function RankingPanel() {
  const [rows, setRows] = useState<RankRow[]>([]);
  const [factors, setFactors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([apiService.getRanking(200), apiService.getRankingFactors()])
      .then(([r, f]) => { setRows(r); setFactors(f.factors); })
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load ranking'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4">
      <div className="flex items-center gap-2">
        <ListOrdered className="w-5 h-5 text-accent-primary" />
        <h2 className="text-lg font-bold text-text-main">Cross-sectional Ranking</h2>
        <span className="text-[11px] text-text-muted">
          Relative strength: each factor z-scored across the universe, combined into a weighted composite
        </span>
      </div>

      {loading && <p className="text-sm text-text-muted">Computing ranking…</p>}
      {error && <p className="text-sm text-rose-400">{error}</p>}

      {!loading && !error && (
        <div className="rounded-xl border border-border-subtle bg-bg-surface/60 overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-text-muted border-b border-border-subtle">
              <tr>
                <th className="text-right px-3 py-2">#</th>
                <th className="text-left px-3 py-2">Symbol</th>
                <th className="text-right px-3 py-2">
                  <span className="inline-flex items-center gap-1">Composite z <ArrowUpDown className="w-3 h-3" /></span>
                </th>
                <th className="text-right px-3 py-2">Pctile</th>
                {factors.map(f => (
                  <th key={f} className="text-right px-3 py-2 capitalize">{f}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.symbol} className="border-b border-border-subtle/50">
                  <td className="px-3 py-1.5 text-right text-text-muted">{i + 1}</td>
                  <td className="px-3 py-1.5 font-semibold">{r.symbol.replace('.NS', '')}</td>
                  <td className={`px-3 py-1.5 text-right font-semibold ${zColor(r.composite_z)}`}>{Z(r.composite_z)}</td>
                  <td className="px-3 py-1.5 text-right text-text-muted">
                    {r.percentile === null ? '—' : r.percentile.toFixed(0)}
                  </td>
                  {factors.map(f => (
                    <td key={f} className={`px-3 py-1.5 text-right ${zColor(r.factors[f])}`}>{Z(r.factors[f])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && rows.length === 0 && (
        <p className="text-xs text-text-muted">No ranked symbols — run a sync first so snapshots have factor scores.</p>
      )}
    </div>
  );
}
