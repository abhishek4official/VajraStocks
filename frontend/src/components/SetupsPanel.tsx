import { useEffect, useState } from 'react';
import { Zap } from 'lucide-react';
import { apiService } from '../services/api';

type Row = Record<string, unknown>;
const num = (v: unknown, d = 2) =>
  typeof v === 'number' ? v.toFixed(d) : v === null || v === undefined ? '—' : String(v);

export function SetupsPanel() {
  const [presets, setPresets] = useState<{ name: string; description: string }[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiService.getPresets().then(setPresets).catch(() => setPresets([]));
  }, []);

  const run = async (name: string) => {
    setActive(name);
    setLoading(true);
    try {
      const res = await apiService.runPreset(name);
      setRows(res.rows);
      setCount(res.count);
    } catch {
      setRows([]);
      setCount(0);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Zap className="w-5 h-5 text-accent-primary" />
        <h2 className="text-lg font-bold text-text-main">Setups</h2>
        <span className="text-[11px] text-text-muted">One-click tradable presets over today's snapshot</span>
      </div>

      {/* Preset chips */}
      <div className="flex flex-wrap gap-2">
        {presets.map(p => (
          <button
            key={p.name}
            onClick={() => run(p.name)}
            title={p.description}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition cursor-pointer ${
              active === p.name
                ? 'bg-accent-primary text-accent-text border-transparent'
                : 'border-border-subtle text-text-muted hover:text-text-main'
            }`}
          >
            {p.name}
          </button>
        ))}
      </div>

      {active && (
        <p className="text-[11px] text-text-muted">
          {presets.find(p => p.name === active)?.description}
        </p>
      )}

      {loading && <p className="text-sm text-text-muted">Scanning…</p>}

      {!loading && active && (
        <div className="space-y-2">
          <div className="text-sm font-semibold text-text-main">{count} match{count === 1 ? '' : 'es'}</div>
          {rows.length > 0 && (
            <div className="rounded-xl border border-border-subtle bg-bg-surface/60 overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-text-muted border-b border-border-subtle">
                  <tr>
                    <th className="text-left px-3 py-2">Symbol</th>
                    <th className="text-right px-3 py-2">Close</th>
                    <th className="text-right px-3 py-2">RSI</th>
                    <th className="text-right px-3 py-2">ADX</th>
                    <th className="text-right px-3 py-2">Stage</th>
                    <th className="text-right px-3 py-2">RS</th>
                    <th className="text-right px-3 py-2">Composite</th>
                    <th className="text-right px-3 py-2">4w ret</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className="border-b border-border-subtle/50">
                      <td className="px-3 py-1.5 font-semibold">{String(r.symbol ?? '').replace('.NS', '')}</td>
                      <td className="px-3 py-1.5 text-right">{num(r.close_price)}</td>
                      <td className="px-3 py-1.5 text-right">{num(r.rsi_14, 1)}</td>
                      <td className="px-3 py-1.5 text-right">{num(r.adx_14, 1)}</td>
                      <td className="px-3 py-1.5 text-right">{num(r.weinstein_stage, 0)}</td>
                      <td className="px-3 py-1.5 text-right">{num(r.rs_score_val, 0)}</td>
                      <td className="px-3 py-1.5 text-right font-semibold text-text-main">{num(r.composite_score, 0)}</td>
                      <td className="px-3 py-1.5 text-right">{typeof r.ret_4w === 'number' ? `${(r.ret_4w * 100).toFixed(1)}%` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {rows.length === 0 && <p className="text-xs text-text-muted">No matches (run a sync so snapshots are current).</p>}
        </div>
      )}
    </div>
  );
}
