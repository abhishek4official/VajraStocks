import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity, AlertTriangle, Brain, CheckCircle2, ChevronDown, ChevronUp,
  Clock, Cpu, History, Play, RefreshCw, StopCircle,
} from 'lucide-react';
import { API_BASE } from '../lib/apiBase';
import type { ML2FoldMetric, ML2ProgressEvent, ML2TrainingRun } from '../services/api';

const BASE = API_BASE;

// ── Helpers ───────────────────────────────────────────────────────────────────

function icColor(ic: number | null | undefined) {
  if (ic == null) return 'text-slate-500';
  if (ic >= 0.15) return 'text-emerald-400';
  if (ic >= 0.05) return 'text-amber-400';
  if (ic >= 0)    return 'text-slate-400';
  return 'text-rose-400';
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    RUNNING:   'bg-purple-500/20 border-purple-400/50 text-purple-200',
    COMPLETED: 'bg-emerald-500/20 border-emerald-400/50 text-emerald-200',
    FAILED:    'bg-rose-500/20 border-rose-400/50 text-rose-200',
    CANCELLED: 'bg-slate-700/40 border-slate-600/40 text-slate-400',
  };
  return map[status] ?? 'bg-slate-700/40 border-slate-600/40 text-slate-400';
}

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function fmtDuration(start: string | null | undefined, end: string | null | undefined) {
  if (!start) return '—';
  const ms = new Date(end ?? new Date().toISOString()).getTime() - new Date(start).getTime();
  const m  = Math.floor(ms / 60000);
  const s  = Math.floor((ms % 60000) / 1000);
  return `${m}m ${s}s`;
}

// ── Fold table ─────────────────────────────────────────────────────────────────

const FoldTable: React.FC<{ folds: ML2FoldMetric[] }> = ({ folds }) => {
  const meanIcPtp = folds.length
    ? folds.reduce((s, f) => s + f.ic_ptp, 0) / folds.length
    : null;
  return (
    <table className="w-full text-xs border-collapse">
      <thead>
        <tr className="text-slate-500 border-b border-slate-800">
          <th className="py-1 px-2 text-left font-mono">Fold</th>
          <th className="py-1 px-2 text-right" title="Spearman IC between P(TP) and actual TP outcome">IC(P_TP)</th>
          <th className="py-1 px-2 text-right" title="Fraction of top-10% ranked stocks that actually hit TP barrier">TP-Prec@10</th>
          <th className="py-1 px-2 text-right" title="Hit rate on top-10% by EV score (positive 5d return)">Hit5d@10</th>
          <th className="py-1 px-2 text-right" title="Long top-decile / short bottom-decile daily return">L/S %</th>
        </tr>
      </thead>
      <tbody>
        {folds.map(f => (
          <tr key={f.fold} className="border-b border-slate-800/50">
            <td className="py-1 px-2 font-mono text-slate-400">{f.fold}</td>
            <td className={`py-1 px-2 text-right font-mono font-bold ${icColor(f.ic_ptp)}`}>
              {f.ic_ptp >= 0 ? '+' : ''}{f.ic_ptp.toFixed(4)}
            </td>
            <td className="py-1 px-2 text-right font-mono text-slate-300">{f.tp_prec.toFixed(1)}%</td>
            <td className="py-1 px-2 text-right font-mono text-slate-300">{f.hit_5d.toFixed(1)}%</td>
            <td className={`py-1 px-2 text-right font-mono ${f.ls_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {f.ls_pnl >= 0 ? '+' : ''}{f.ls_pnl.toFixed(2)}%
            </td>
          </tr>
        ))}
        {folds.length > 1 && (
          <tr className="border-t border-slate-700 bg-slate-900/40">
            <td className="py-1 px-2 font-mono text-slate-500">Mean</td>
            <td className={`py-1 px-2 text-right font-mono font-bold ${icColor(meanIcPtp)}`}>
              {meanIcPtp != null ? `${meanIcPtp >= 0 ? '+' : ''}${meanIcPtp.toFixed(4)}` : '—'}
            </td>
            <td colSpan={3} />
          </tr>
        )}
      </tbody>
    </table>
  );
};

// ── Component ─────────────────────────────────────────────────────────────────

export const ML2TrainingPanel: React.FC = () => {
  const [isTraining,   setIsTraining]   = useState(false);
  const [pct,          setPct]          = useState(0);
  const [stage,        setStage]        = useState('');
  const [datasetInfo,  setDatasetInfo]  = useState<{ rows: number; features: number; date_start: string; date_end: string } | null>(null);
  const [foldMetrics,  setFoldMetrics]  = useState<ML2FoldMetric[]>([]);
  const [currentFold,  setCurrentFold]  = useState<number>(0);
  const [totalFolds,   setTotalFolds]   = useState<number>(0);
  const [treeProgress, setTreeProgress] = useState<{ tree: number; total: number } | null>(null);
  const [logs,         setLogs]         = useState<string[]>([]);
  const [error,        setError]        = useState<string | null>(null);
  const [latestRun,    setLatestRun]    = useState<ML2TrainingRun | null>(null);
  const [history,      setHistory]      = useState<ML2TrainingRun[]>([]);
  const [showHistory,  setShowHistory]  = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  const esRef     = useRef<EventSource | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((msg: string) => {
    const ts = new Date().toLocaleTimeString('en-IN', { hour12: false });
    setLogs(l => [...l.slice(-500), `[${ts}] ${msg}`]);
  }, []);

  const fetchLatest = useCallback(async () => {
    try {
      const r = await fetch(`${BASE}/ml2/latest`);
      if (r.ok) setLatestRun(await r.json());
    } catch { /* silent */ }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const r = await fetch(`${BASE}/ml2/history`);
      if (r.ok) setHistory(await r.json());
    } catch { /* silent */ }
  }, []);

  const openStream = useCallback(() => {
    if (esRef.current) esRef.current.close();
    const es = new EventSource(`${BASE}/ml2/train/stream`);
    esRef.current = es;

    es.onmessage = (e: MessageEvent) => {
      let evt: ML2ProgressEvent;
      try { evt = JSON.parse(e.data); } catch { return; }

      if (evt.pct != null) setPct(evt.pct);

      switch (evt.type) {
        case 'stage':
          setStage(evt.message ?? '');
          addLog(evt.message ?? '');
          break;

        case 'dataset':
          setDatasetInfo({
            rows:       evt.rows ?? 0,
            features:   evt.features ?? 0,
            date_start: evt.date_start ?? '',
            date_end:   evt.date_end   ?? '',
          });
          addLog(`Dataset: ${(evt.rows ?? 0).toLocaleString()} rows x ${evt.features} features (${evt.date_start} -> ${evt.date_end})`);
          break;

        case 'fold_start':
          setCurrentFold(evt.fold ?? 0);
          setTotalFolds(evt.total ?? 0);
          setTreeProgress(null);
          setStage(`Fold ${evt.fold}/${evt.total}: LightGBM (CPU)...`);
          addLog(`Fold ${evt.fold}/${evt.total} — train ${(evt.train_rows ?? 0).toLocaleString()} rows | test ${(evt.test_rows ?? 0).toLocaleString()} rows`);
          break;

        case 'tree':
          setTreeProgress({ tree: evt.tree ?? 0, total: evt.total ?? 800 });
          break;

        case 'fold_done':
          setFoldMetrics(prev => {
            const next = prev.filter(f => f.fold !== evt.fold);
            return [...next, {
              fold:    evt.fold    ?? 0,
              ic_ptp:  evt.ic_ptp  ?? 0,
              tp_prec: evt.tp_prec ?? 0,
              hit_5d:  evt.hit_5d  ?? 0,
              ls_pnl:  evt.ls_pnl  ?? 0,
            }].sort((a, b) => a.fold - b.fold);
          });
          addLog(`Fold ${evt.fold} done — IC(P_TP) ${(evt.ic_ptp ?? 0) >= 0 ? '+' : ''}${(evt.ic_ptp ?? 0).toFixed(4)}  TP-Prec ${(evt.tp_prec ?? 0).toFixed(1)}%  Hit5d ${(evt.hit_5d ?? 0).toFixed(1)}%  L/S ${(evt.ls_pnl ?? 0) >= 0 ? '+' : ''}${(evt.ls_pnl ?? 0).toFixed(2)}%`);
          break;

        case 'complete':
          setStage('Training complete');
          setIsTraining(false);
          setIsCancelling(false);
          addLog(`Training complete — Mean IC(P_TP) ${(evt.mean_ic_ptp ?? 0) >= 0 ? '+' : ''}${(evt.mean_ic_ptp ?? 0).toFixed(4)}  Mean TP-Prec ${(evt.mean_tp_prec ?? 0).toFixed(1)}% across ${evt.folds} folds`);
          fetchLatest();
          fetchHistory();
          es.close();
          break;

        case 'cancelled':
          setStage('Training cancelled');
          setIsTraining(false);
          setIsCancelling(false);
          addLog('Training cancelled by user');
          fetchHistory();
          es.close();
          break;

        case 'error':
          setError(evt.error ?? evt.message ?? 'Unknown error');
          setStage('Training failed');
          setIsTraining(false);
          setIsCancelling(false);
          addLog(`ERROR: ${evt.error ?? evt.message}`);
          fetchHistory();
          es.close();
          break;

        case 'stream_end':
          es.close();
          break;

        case 'heartbeat':
          break;
      }
    };

    es.onerror = () => { if (!isTraining) es.close(); };
  }, [addLog, fetchHistory, fetchLatest, isTraining]);

  useEffect(() => {
    fetchLatest();
    fetchHistory();
    (async () => {
      try {
        const r = await fetch(`${BASE}/ml2/train/status`);
        if (!r.ok) return;
        const d = await r.json();
        if (d.status === 'running') { setIsTraining(true); openStream(); }
      } catch { /* silent */ }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs]);
  useEffect(() => () => { esRef.current?.close(); }, []);

  const handleTrain = async () => {
    setError(null);
    setLogs([]);
    setFoldMetrics([]);
    setDatasetInfo(null);
    setTreeProgress(null);
    setPct(0);
    setCurrentFold(0);
    setTotalFolds(0);
    setStage('Starting...');
    try {
      const r = await fetch(`${BASE}/ml2/train`, { method: 'POST' });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail ?? `HTTP ${r.status}`);
      }
      const d = await r.json();
      setIsTraining(true);
      addLog(`V2 training job started — version ${d.version} (run #${d.run_id})`);
      openStream();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setStage('');
      setIsTraining(false);
    }
  };

  const handleCancel = async () => {
    setIsCancelling(true);
    try {
      await fetch(`${BASE}/ml2/train`, { method: 'DELETE' });
      addLog('Cancellation requested...');
    } catch { setIsCancelling(false); }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-600/10 border border-emerald-500/30 rounded-xl text-emerald-400">
            <Brain className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-text-main">VajraML2 Training</h2>
            <p className="text-xs text-slate-500">Triple-Barrier Classifier — 6-fold walk-forward (CPU only)</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isTraining ? (
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-rose-600/20 border border-rose-500/40 text-rose-300 hover:bg-rose-600/30 text-sm font-bold transition disabled:opacity-50 cursor-pointer"
            >
              <StopCircle className="w-4 h-4" />
              {isCancelling ? 'Cancelling…' : 'Cancel Training'}
            </button>
          ) : (
            <button
              onClick={handleTrain}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-sm font-bold transition shadow-lg shadow-emerald-900/30 cursor-pointer"
            >
              <Play className="w-4 h-4" />
              Train V2 Model
            </button>
          )}
        </div>
      </div>

      {/* V2 model info box */}
      <div className="p-3 rounded-lg border border-border-subtle bg-bg-surface/30 text-xs text-slate-500 space-y-1">
        <p><span className="text-text-muted font-semibold">Signal grades:</span> Strong Buy (dual-model agree + volume + P(TP) ≥ 45%) · Buy (P(TP) ≥ 40%) · Watch (EV &gt; 0) · Avoid · Market Risk (regime gate)</p>
        <p><span className="text-text-muted font-semibold">Training time:</span> ~90 min on CPU across 6 folds (~490K rows × 80 features)</p>
        <p><span className="text-text-muted font-semibold">Target:</span> TP = close + 1.5×ATR · SL = close – 1.0×ATR · horizon = 5 trading days</p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-rose-950/30 border border-rose-500/40 text-rose-300 text-sm">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Active training card */}
      {(isTraining || pct > 0) && (
        <div className="rounded-xl border border-emerald-500/30 bg-bg-surface p-5 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2 text-sm">
              {isTraining
                ? <RefreshCw className="w-4 h-4 text-emerald-400 animate-spin" />
                : <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
              <span className="text-text-main font-medium">{stage || 'Initialising…'}</span>
            </div>
            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded border text-xs font-bold bg-slate-700/40 border-slate-600/40 text-slate-400">
              <Cpu className="w-3 h-3" />
              CPU
            </span>
          </div>

          {/* Progress bar */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-slate-500">
              <span>
                {currentFold > 0 && totalFolds > 0
                  ? `Fold ${currentFold} / ${totalFolds}`
                  : 'Preparing…'}
                {treeProgress && isTraining
                  ? ` — tree ${treeProgress.tree}/${treeProgress.total}`
                  : ''}
              </span>
              <span className="font-mono text-emerald-400">{pct}%</span>
            </div>
            <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-700 to-emerald-400 transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {/* Dataset info */}
          {datasetInfo && (
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
              <span><span className="text-slate-300 font-mono">{datasetInfo.rows.toLocaleString()}</span> rows</span>
              <span><span className="text-slate-300 font-mono">{datasetInfo.features}</span> features</span>
              <span><span className="text-slate-300 font-mono">{datasetInfo.date_start}</span> → <span className="text-slate-300 font-mono">{datasetInfo.date_end}</span></span>
            </div>
          )}

          {/* Live fold metrics */}
          {foldMetrics.length > 0 && (
            <div className="overflow-x-auto">
              <FoldTable folds={foldMetrics} />
            </div>
          )}
        </div>
      )}

      {/* Last trained model info */}
      {latestRun && !isTraining && (
        <div className="rounded-xl border border-border-subtle bg-bg-surface p-4">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-bold text-text-main">Active V2 Model</span>
            <span className={`ml-auto px-2 py-0.5 rounded border text-[10px] font-bold ${statusBadge(latestRun.status)}`}>
              {latestRun.status}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Version',    value: latestRun.version },
              { label: 'Trained',    value: fmtDate(latestRun.completed_at) },
              { label: 'Duration',   value: fmtDuration(latestRun.started_at, latestRun.completed_at) },
              { label: 'Folds',      value: latestRun.num_folds?.toString() ?? '—' },
              { label: 'Dataset',    value: latestRun.dataset_rows ? `${latestRun.dataset_rows.toLocaleString()} rows` : '—' },
              { label: 'Date Range', value: latestRun.date_range_start && latestRun.date_range_end ? `${latestRun.date_range_start} -> ${latestRun.date_range_end}` : '—' },
              { label: 'Mean IC(P_TP)', value: latestRun.mean_ic_ptp != null ? `${latestRun.mean_ic_ptp >= 0 ? '+' : ''}${latestRun.mean_ic_ptp.toFixed(4)}` : '—', highlight: true },
            ].map(({ label, value, highlight }) => (
              <div key={label}>
                <p className="text-[10px] text-slate-600 uppercase tracking-wider">{label}</p>
                <p className={`text-xs font-mono font-semibold mt-0.5 ${highlight ? icColor(latestRun.mean_ic_ptp) : 'text-slate-300'}`}>{value}</p>
              </div>
            ))}
          </div>

          {latestRun.fold_metrics && latestRun.fold_metrics.length > 0 && (
            <div className="mt-3 overflow-x-auto">
              <FoldTable folds={latestRun.fold_metrics} />
            </div>
          )}
        </div>
      )}

      {/* Training log */}
      {logs.length > 0 && (
        <div className="rounded-xl border border-border-subtle bg-bg-base">
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border-subtle">
            <Activity className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-xs font-bold text-text-muted">Training Log</span>
            <span className="ml-auto text-[10px] text-slate-600 font-mono">{logs.length} lines</span>
          </div>
          <div className="h-48 overflow-y-auto p-3 font-mono text-[11px] text-slate-400 space-y-0.5">
            {logs.map((line, i) => (
              <div key={i} className={
                line.includes('ERROR') ? 'text-rose-400' :
                line.includes('done') || line.includes('complete') ? 'text-emerald-400' :
                line.includes('Fold') ? 'text-emerald-300' :
                'text-slate-400'
              }>{line}</div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {/* History */}
      <div className="rounded-xl border border-border-subtle bg-bg-surface">
        <button
          onClick={() => { setShowHistory(h => !h); if (!showHistory) fetchHistory(); }}
          className="w-full flex items-center gap-2 px-4 py-3 text-sm font-bold text-text-muted hover:text-text-main transition cursor-pointer"
        >
          <History className="w-4 h-4 text-slate-500" />
          V2 Training History
          <span className="ml-2 text-[10px] font-normal text-slate-500">({history.length} runs)</span>
          {showHistory
            ? <ChevronUp className="w-3.5 h-3.5 ml-auto text-slate-600" />
            : <ChevronDown className="w-3.5 h-3.5 ml-auto text-slate-600" />}
        </button>

        {showHistory && (
          <div className="border-t border-slate-800 overflow-x-auto">
            {history.length === 0 ? (
              <p className="text-xs text-slate-600 text-center py-6">No V2 training history yet.</p>
            ) : (
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800 text-left">
                    <th className="py-2 px-3">Version</th>
                    <th className="py-2 px-3">Status</th>
                    <th className="py-2 px-3 text-right">Folds</th>
                    <th className="py-2 px-3 text-right">Mean IC(P_TP)</th>
                    <th className="py-2 px-3 text-right">Rows</th>
                    <th className="py-2 px-3">Duration</th>
                    <th className="py-2 px-3">Started</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {history.map(run => (
                    <tr key={run.id} className="hover:bg-slate-900/40 transition">
                      <td className="py-2 px-3 font-mono text-emerald-300">{run.version}</td>
                      <td className="py-2 px-3">
                        <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${statusBadge(run.status)}`}>
                          {run.status}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-slate-400">{run.num_folds ?? '—'}</td>
                      <td className={`py-2 px-3 text-right font-mono font-bold ${icColor(run.mean_ic_ptp)}`}>
                        {run.mean_ic_ptp != null ? `${run.mean_ic_ptp >= 0 ? '+' : ''}${run.mean_ic_ptp.toFixed(4)}` : '—'}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-slate-500">
                        {run.dataset_rows ? run.dataset_rows.toLocaleString() : '—'}
                      </td>
                      <td className="py-2 px-3 font-mono text-slate-500">
                        {fmtDuration(run.started_at, run.completed_at)}
                      </td>
                      <td className="py-2 px-3 text-slate-500 whitespace-nowrap">
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {fmtDate(run.started_at)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
