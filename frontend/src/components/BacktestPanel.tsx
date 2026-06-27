import { useEffect, useState } from 'react';
import { Play, History, TrendingUp, AlertTriangle, Database } from 'lucide-react';
import {
  apiService,
  type BacktestRunResult,
  type BacktestMetrics,
  type SavedBacktestRun,
} from '../services/api';

const PCT = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(2)}%`;
const NUM = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined ? '∞' : v.toFixed(d);

// Default param inputs per setup. Adding a signal here is the only UI change needed.
const PARAM_FIELDS: Record<string, { key: string; label: string; def: number }[]> = {
  sma_crossover: [
    { key: 'fast', label: 'Fast SMA', def: 20 },
    { key: 'slow', label: 'Slow SMA', def: 50 },
  ],
  ema_crossover: [
    { key: 'fast', label: 'Fast EMA', def: 12 },
    { key: 'slow', label: 'Slow EMA', def: 26 },
  ],
  breakout: [
    { key: 'entry_lookback', label: 'Entry lookback', def: 20 },
    { key: 'exit_lookback', label: 'Exit lookback', def: 10 },
  ],
};

function MetricCard({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-bg-surface/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-text-muted">{label}</div>
      <div className={`text-lg font-bold ${danger ? 'text-rose-400' : 'text-text-main'}`}>{value}</div>
    </div>
  );
}

function MetricsGrid({ m }: { m: BacktestMetrics }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
      <MetricCard label="Total return" value={PCT(m.total_return)} />
      <MetricCard label="CAGR" value={PCT(m.cagr)} />
      <MetricCard label="Max drawdown" value={PCT(m.max_drawdown)} danger />
      <MetricCard label="Sharpe" value={NUM(m.sharpe_ratio)} />
      <MetricCard label="Win rate" value={PCT(m.win_rate)} />
      <MetricCard label="Profit factor" value={NUM(m.profit_factor)} />
      <MetricCard label="Trades" value={String(m.trades)} />
    </div>
  );
}

export function BacktestPanel() {
  const [signals, setSignals] = useState<string[]>([]);
  const [symbol, setSymbol] = useState('RELIANCE');
  const [signal, setSignal] = useState('sma_crossover');
  const [params, setParams] = useState<Record<string, number>>({ fast: 20, slow: 50 });
  const [stopPct, setStopPct] = useState('');
  const [targetPct, setTargetPct] = useState('');
  const [costBps, setCostBps] = useState('0');
  const [adjusted, setAdjusted] = useState(true);
  const [save, setSave] = useState(true);

  const [result, setResult] = useState<BacktestRunResult | null>(null);
  const [runs, setRuns] = useState<SavedBacktestRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backfilling, setBackfilling] = useState(false);
  const [backfillMsg, setBackfillMsg] = useState<string | null>(null);

  const refreshRuns = () => {
    apiService.listBacktestRuns().then(setRuns).catch(() => setRuns([]));
  };

  useEffect(() => {
    apiService.getBacktestSignals().then(setSignals).catch(() => setSignals(['sma_crossover', 'breakout']));
    refreshRuns();
  }, []);

  // Switch setup and reset its params to defaults in one handler (no setState-in-effect).
  const selectSignal = (s: string) => {
    setSignal(s);
    const fields = PARAM_FIELDS[s] ?? [];
    setParams(Object.fromEntries(fields.map(f => [f.key, f.def])));
  };

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiService.runBacktest({
        symbol,
        signal,
        params,
        stop_pct: stopPct ? Number(stopPct) : null,
        target_pct: targetPct ? Number(targetPct) : null,
        cost_bps: Number(costBps) || 0,
        adjusted,
        save,
      });
      setResult(res);
      if (save) refreshRuns();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Backtest failed');
    } finally {
      setLoading(false);
    }
  };

  const backfill = async () => {
    setBackfilling(true);
    setBackfillMsg('Queued…');
    try {
      // Run via the background worker so it doesn't block and can't collide with a sync.
      const job = await apiService.enqueueJob('columnar_backfill', { incremental: true });
      // Poll progress until the job finishes.
      for (;;) {
        await new Promise(res => setTimeout(res, 1500));
        const j = await apiService.getJob(job.id);
        if (j.status === 'RUNNING' && j.progress_total) {
          setBackfillMsg(`Mirroring… ${j.progress_current}/${j.progress_total}`);
        } else if (j.status === 'SUCCESS') {
          setBackfillMsg('Backfill complete.');
          break;
        } else if (j.status === 'FAILED' || j.status === 'CANCELLED') {
          setBackfillMsg(j.status === 'FAILED' ? `Backfill failed: ${j.error ?? ''}` : 'Backfill cancelled.');
          break;
        }
      }
    } catch (e) {
      setBackfillMsg(e instanceof Error ? e.message : 'Backfill failed');
    } finally {
      setBackfilling(false);
    }
  };

  const fields = PARAM_FIELDS[signal] ?? [];

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-5">
      <div className="flex items-center gap-2">
        <TrendingUp className="w-5 h-5 text-accent-primary" />
        <h2 className="text-lg font-bold text-text-main">Backtest Lab</h2>
        <span className="text-[11px] text-text-muted">
          Reproducible event-driven backtest over adjusted history
        </span>
      </div>

      {/* Controls */}
      <div className="rounded-xl border border-border-subtle bg-bg-surface/60 p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Symbol
          <input
            value={symbol}
            onChange={e => setSymbol(e.target.value.toUpperCase())}
            className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-sm text-text-main"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Setup
          <select
            value={signal}
            onChange={e => selectSignal(e.target.value)}
            className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-sm text-text-main"
          >
            {signals.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        {fields.map(f => (
          <label key={f.key} className="flex flex-col gap-1 text-[11px] text-text-muted">
            {f.label}
            <input
              type="number"
              value={params[f.key] ?? f.def}
              onChange={e => setParams(p => ({ ...p, [f.key]: Number(e.target.value) }))}
              className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-sm text-text-main"
            />
          </label>
        ))}
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Stop % (e.g. 0.05)
          <input
            value={stopPct}
            onChange={e => setStopPct(e.target.value)}
            placeholder="none"
            className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-sm text-text-main"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Target % (e.g. 0.10)
          <input
            value={targetPct}
            onChange={e => setTargetPct(e.target.value)}
            placeholder="none"
            className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-sm text-text-main"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Cost (bps)
          <input
            value={costBps}
            onChange={e => setCostBps(e.target.value)}
            className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-sm text-text-main"
          />
        </label>
        <div className="flex items-end gap-3 text-[11px] text-text-muted">
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={adjusted} onChange={e => setAdjusted(e.target.checked)} />
            Adjusted
          </label>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={save} onChange={e => setSave(e.target.checked)} />
            Save
          </label>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={run}
          disabled={loading || !symbol}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-primary text-accent-text text-sm font-bold disabled:opacity-50 cursor-pointer"
        >
          <Play className="w-4 h-4" />
          {loading ? 'Running…' : 'Run backtest'}
        </button>
        <button
          onClick={backfill}
          disabled={backfilling}
          title="Mirror your synced price history into the columnar store (needed once before backtests have data)."
          className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border-subtle text-text-muted hover:text-text-main text-sm disabled:opacity-50 cursor-pointer"
        >
          <Database className="w-4 h-4" />
          {backfilling ? 'Backfilling…' : 'Backfill data'}
        </button>
        {backfillMsg && <span className="text-[11px] text-text-muted">{backfillMsg}</span>}
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-lg px-3 py-2">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-3">
          <div className="text-sm font-semibold text-text-main">
            {result.symbol} · {result.signal} · {result.bars} bars
            {result.run_id ? <span className="text-text-muted"> · saved #{result.run_id}</span> : null}
          </div>
          <MetricsGrid m={result.metrics} />

          {result.trades.length > 0 && (
            <div className="rounded-xl border border-border-subtle bg-bg-surface/60 overflow-hidden">
              <table className="w-full text-xs">
                <thead className="text-text-muted border-b border-border-subtle">
                  <tr>
                    <th className="text-left px-3 py-2">Entry</th>
                    <th className="text-right px-3 py-2">Entry px</th>
                    <th className="text-left px-3 py-2">Exit</th>
                    <th className="text-right px-3 py-2">Exit px</th>
                    <th className="text-right px-3 py-2">Return</th>
                    <th className="text-left px-3 py-2">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((t, i) => (
                    <tr key={i} className="border-b border-border-subtle/50">
                      <td className="px-3 py-1.5 text-text-muted">{t.entry_date}</td>
                      <td className="px-3 py-1.5 text-right">{t.entry_price.toFixed(2)}</td>
                      <td className="px-3 py-1.5 text-text-muted">{t.exit_date}</td>
                      <td className="px-3 py-1.5 text-right">{t.exit_price.toFixed(2)}</td>
                      <td className={`px-3 py-1.5 text-right font-semibold ${t.return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {PCT(t.return_pct)}
                      </td>
                      <td className="px-3 py-1.5 text-text-muted">{t.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Saved runs */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-text-main">
          <History className="w-4 h-4" /> Saved runs
        </div>
        {runs.length === 0 ? (
          <p className="text-xs text-text-muted">No saved runs yet.</p>
        ) : (
          <div className="rounded-xl border border-border-subtle bg-bg-surface/60 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="text-text-muted border-b border-border-subtle">
                <tr>
                  <th className="text-left px-3 py-2">#</th>
                  <th className="text-left px-3 py-2">Symbol</th>
                  <th className="text-left px-3 py-2">Setup</th>
                  <th className="text-right px-3 py-2">Total</th>
                  <th className="text-right px-3 py-2">Sharpe</th>
                  <th className="text-right px-3 py-2">Trades</th>
                  <th className="text-left px-3 py-2">When</th>
                </tr>
              </thead>
              <tbody>
                {runs.map(r => (
                  <tr key={r.id} className="border-b border-border-subtle/50">
                    <td className="px-3 py-1.5 text-text-muted">{r.id}</td>
                    <td className="px-3 py-1.5">{r.symbol}</td>
                    <td className="px-3 py-1.5 text-text-muted">{r.signal}</td>
                    <td className="px-3 py-1.5 text-right">{PCT(r.metrics.total_return)}</td>
                    <td className="px-3 py-1.5 text-right">{NUM(r.metrics.sharpe_ratio)}</td>
                    <td className="px-3 py-1.5 text-right">{r.trades_count}</td>
                    <td className="px-3 py-1.5 text-text-muted">{new Date(r.created_at).toLocaleString('en-IN')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
