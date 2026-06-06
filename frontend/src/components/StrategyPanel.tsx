import React, { useEffect, useMemo, useState } from 'react';
import { useStockStore } from '../store/useStockStore';
import { apiService } from '../services/api';
import type { StrategyMeta, StrategySignalsResponse } from '../services/api';
import {
  Play, RefreshCw, Download, AlertTriangle, ChevronDown, ChevronRight,
  Target, Bookmark, Sliders,
} from 'lucide-react';

type SignalKind = 'BUY' | 'WATCH' | 'SELL' | 'NONE';
const ALL_SIGNALS: SignalKind[] = ['BUY', 'WATCH', 'SELL', 'NONE'];
const SIGNAL_LABEL: Record<SignalKind, string> = { BUY: 'BUY', WATCH: 'WATCH', SELL: 'SELL', NONE: 'Near-miss' };

const SIGNAL_STYLE: Record<string, string> = {
  BUY: 'text-emerald-400 bg-emerald-950/30 border-emerald-800/50',
  WATCH: 'text-amber-400 bg-amber-950/30 border-amber-800/50',
  SELL: 'text-rose-400 bg-rose-950/30 border-rose-800/50',
  NONE: 'text-slate-400 bg-slate-900/30 border-slate-700',
};

type SortField = 'score' | 'symbol' | 'last_close' | 'rr' | 'risk_pct';

export const StrategyPanel: React.FC = () => {
  const { setActiveTab, setSelectedSymbol, watchlists, activeWatchlistId, addToWatchlist } = useStockStore();

  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [strategyId, setStrategyId] = useState<string>('');
  const [signals, setSignals] = useState<StrategySignalsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  const [selectedSignals, setSelectedSignals] = useState<SignalKind[]>(['BUY', 'WATCH']);
  const [minScore, setMinScore] = useState(70);
  const [showParams, setShowParams] = useState(false);
  const [paramValues, setParamValues] = useState<Record<string, number | string | boolean>>({});
  const [forceMarketOk, setForceMarketOk] = useState(false);
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const activeStrategy = useMemo(
    () => strategies.find(s => s.id === strategyId) || null,
    [strategies, strategyId],
  );

  // Initialise editable params from the strategy's schema defaults.
  const resetParams = (strat = activeStrategy) => {
    if (!strat) return;
    const defaults: Record<string, number | string | boolean> = {};
    for (const [key, spec] of Object.entries(strat.param_schema)) {
      defaults[key] = spec.type === 'number' ? Number(spec.default)
        : spec.type === 'boolean' ? Boolean(spec.default)
        : String(spec.default ?? '');
    }
    setParamValues(defaults);
  };
  useEffect(() => { resetParams(); /* eslint-disable-next-line */ }, [activeStrategy]);

  const dirtyParams = useMemo(() => {
    if (!activeStrategy) return false;
    return Object.entries(paramValues).some(([k, v]) => {
      const spec = activeStrategy.param_schema[k];
      if (!spec) return false;
      const def = spec.type === 'number' ? Number(spec.default)
        : spec.type === 'boolean' ? Boolean(spec.default) : String(spec.default ?? '');
      return def !== v;
    });
  }, [activeStrategy, paramValues]);

  // Load registry once.
  useEffect(() => {
    apiService.getStrategies()
      .then(list => {
        setStrategies(list);
        if (list.length) setStrategyId(list[0].id);
      })
      .catch(() => setStrategies([]));
  }, []);

  const loadSignals = async (id = strategyId) => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await apiService.getStrategySignals(id, {
        signal: selectedSignals.join(','),
        min_score: minScore,
        limit: 2500,
      });
      setSignals(res);
    } catch {
      setSignals(null);
    } finally {
      setLoading(false);
    }
  };

  // Reload when strategy / filters change.
  useEffect(() => {
    if (strategyId) loadSignals(strategyId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyId, selectedSignals, minScore]);

  const handleRecompute = async () => {
    if (!strategyId) return;
    setRecomputing(true);
    // Baseline signature so we can detect when the background rebuild lands.
    const sigOf = (c: Record<string, number>) => `${c.BUY ?? 0}/${c.WATCH ?? 0}/${c.SELL ?? 0}/${c.scanned ?? 0}`;
    const baseline = sigOf(signals?.counts ?? {});
    try {
      await apiService.recomputeStrategy(strategyId, paramValues, forceMarketOk);
    } catch {
      setRecomputing(false);
      return;
    }
    // The materializer commits the whole universe at once (can take a few minutes
    // on the full list), so poll until the counts change or we hit the cap.
    let attempts = 0;
    const poll = async () => {
      attempts += 1;
      try {
        const res = await apiService.getStrategySignals(strategyId, {
          signal: selectedSignals.join(','), min_score: minScore, limit: 2500,
        });
        setSignals(res);
        if (sigOf(res.counts) !== baseline || attempts >= 30) { setRecomputing(false); return; }
      } catch { /* keep polling */ }
      setTimeout(poll, 6000);
    };
    setTimeout(poll, 6000);
  };

  const toggleSignal = (s: SignalKind) =>
    setSelectedSignals(prev => (prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]));

  const rows = useMemo(() => {
    let r = signals?.rows ?? [];
    if (search.trim()) {
      const q = search.toLowerCase();
      r = r.filter(x =>
        x.symbol.toLowerCase().includes(q) || x.company_name.toLowerCase().includes(q));
    }
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...r].sort((a, b) => {
      const av = a[sortField] ?? (sortField === 'symbol' ? '' : -Infinity);
      const bv = b[sortField] ?? (sortField === 'symbol' ? '' : -Infinity);
      if (typeof av === 'string' || typeof bv === 'string') return String(av).localeCompare(String(bv)) * dir;
      return ((av as number) - (bv as number)) * dir;
    });
  }, [signals, search, sortField, sortDir]);

  const setSort = (f: SortField) => {
    if (sortField === f) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortField(f); setSortDir(f === 'symbol' ? 'asc' : 'desc'); }
  };

  const num = (v: number | null | undefined, d = 2) =>
    v === null || v === undefined ? '-' : Number(v).toFixed(d);
  const pct = (v: number | null | undefined) =>
    v === null || v === undefined ? '-' : `${(v * 100).toFixed(1)}%`;

  const openSymbol = async (symbol: string) => {
    await setSelectedSymbol(symbol);
    setActiveTab('explorer');
  };

  const exportCsv = () => {
    if (!rows.length) return;
    const head = ['Symbol', 'Company', 'Signal', 'Score', 'As of', 'Last close',
      'Entry', 'Stop', 'Target', 'Risk %', 'R:R', 'Reasons'];
    const lines = rows.map(r => [
      r.symbol.replace('.NS', ''), `"${r.company_name}"`, r.signal, num(r.score, 1),
      r.as_of, num(r.last_close), num(r.entry_ref), num(r.initial_stop), num(r.target),
      r.risk_pct === null ? '' : (r.risk_pct * 100).toFixed(1),
      num(r.rr), `"${(r.reasons || []).join(' | ')}"`,
    ].join(','));
    const blob = new Blob([[head.join(','), ...lines].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${strategyId}_signals_${signals?.as_of ?? 'latest'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const counts = signals?.counts ?? {};
  const groupedParams = useMemo(() => {
    const groups: Record<string, [string, StrategyMeta['param_schema'][string]][]> = {};
    if (!activeStrategy) return groups;
    for (const [key, spec] of Object.entries(activeStrategy.param_schema)) {
      const g = spec.group || 'General';
      (groups[g] ||= []).push([key, spec]);
    }
    return groups;
  }, [activeStrategy]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden p-4 gap-4">
      {/* Header / controls */}
      <div className="flex flex-col gap-3 p-4 rounded-xl border border-slate-800/80 bg-[#121620]/40">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">Strategy Screener</h2>
            {activeStrategy && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
                v{activeStrategy.version}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => loadSignals()}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </button>
            <label
              title="Bypass the market-regime gate so BUY entries can fire regardless of NIFTY trend / breadth"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-bold rounded-lg border cursor-pointer transition ${
                forceMarketOk
                  ? 'text-amber-300 bg-amber-950/30 border-amber-700/60'
                  : 'text-slate-400 bg-slate-900/40 border-slate-800 hover:text-slate-200'
              }`}
            >
              <input
                type="checkbox"
                checked={forceMarketOk}
                onChange={e => setForceMarketOk(e.target.checked)}
                className="accent-amber-500 cursor-pointer"
              />
              Force MARKET_OK
            </label>
            <button
              onClick={handleRecompute}
              disabled={recomputing}
              title="Recompute signals from latest stored prices"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-purple-600 hover:bg-purple-500 text-white transition cursor-pointer disabled:opacity-50"
            >
              <Play className={`w-3.5 h-3.5 ${recomputing ? 'animate-pulse' : ''}`} />
              {recomputing ? 'Recomputing…' : 'Recompute'}
            </button>
          </div>
        </div>

        {/* Strategy + filters row */}
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase font-bold text-slate-500">Strategy</label>
            <select
              value={strategyId}
              onChange={e => setStrategyId(e.target.value)}
              className="px-3 py-1.5 text-sm rounded-lg bg-slate-900/80 border border-slate-800 text-white focus:outline-none focus:border-purple-500"
            >
              {strategies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase font-bold text-slate-500">Signals</label>
            <div className="flex gap-1">
              {ALL_SIGNALS.map(s => (
                <button
                  key={s}
                  onClick={() => toggleSignal(s)}
                  title={s === 'NONE' ? 'Names that failed a hard gate, ranked by quality score' : undefined}
                  className={`px-2.5 py-1.5 text-[11px] font-bold rounded-md border transition cursor-pointer ${
                    selectedSignals.includes(s) ? SIGNAL_STYLE[s] : 'text-slate-500 bg-slate-900/40 border-slate-800'
                  }`}
                >
                  {SIGNAL_LABEL[s]}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1 min-w-[180px]">
            <label className="text-[10px] uppercase font-bold text-slate-500">Min score: {minScore}</label>
            <input
              type="range" min={0} max={100} value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
              className="accent-purple-500 cursor-pointer"
            />
          </div>

          <div className="flex flex-col gap-1 flex-1 min-w-[160px]">
            <label className="text-[10px] uppercase font-bold text-slate-500">Search</label>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Symbol or company…"
              className="px-3 py-1.5 text-sm rounded-lg bg-slate-900/80 border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-purple-500"
            />
          </div>

          <button
            onClick={exportCsv}
            disabled={!rows.length}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition cursor-pointer disabled:opacity-40"
          >
            <Download className="w-3.5 h-3.5" /> CSV
          </button>

          <button
            onClick={() => setShowParams(v => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
          >
            <Sliders className="w-3.5 h-3.5" /> Params
          </button>
        </div>

        {/* Counts + staleness banner */}
        <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
          <div className="flex items-center gap-3 text-slate-400">
            <span>{counts.scanned ?? 0} scanned</span>
            <span className="text-emerald-400 font-semibold">{counts.BUY ?? 0} BUY</span>
            <span className="text-amber-400 font-semibold">{counts.WATCH ?? 0} WATCH</span>
            <span className="text-rose-400 font-semibold">{counts.SELL ?? 0} SELL</span>
            {signals?.as_of && <span className="text-slate-500">· as-of {signals.as_of}</span>}
          </div>
          {signals?.stale && (
            <div className="flex items-center gap-1.5 text-amber-400 bg-amber-950/30 border border-amber-800/40 px-2 py-1 rounded-md">
              <AlertTriangle className="w-3.5 h-3.5" />
              Signals are stale — recompute after the latest sync.
            </div>
          )}
        </div>

        {/* Auto-rendered, editable param schema */}
        {showParams && activeStrategy && (
          <div className="pt-2 border-t border-slate-800/60">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase font-bold text-slate-500">
                Parameters {dirtyParams && <span className="text-amber-400">· modified — click Recompute to apply</span>}
              </span>
              <button
                onClick={() => resetParams()}
                className="text-[10px] font-bold text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                Reset to defaults
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {Object.entries(groupedParams).map(([group, items]) => (
                <div key={group} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                  <div className="text-[10px] uppercase font-bold text-purple-400 mb-2">{group}</div>
                  <ul className="flex flex-col gap-1.5">
                    {items.map(([key, spec]) => {
                      const numDefault = Number(spec.default);
                      const step = (spec.maximum !== undefined && spec.minimum !== undefined
                        && spec.maximum - spec.minimum <= 1) ? 0.01 : (numDefault < 5 ? 0.1 : 1);
                      const raw = paramValues[key];
                      return (
                        <li key={key} className="flex items-center justify-between gap-2 text-[11px]" title={spec.description}>
                          <span className="text-slate-400 truncate">{key}</span>
                          {spec.type === 'boolean' ? (
                            <input
                              type="checkbox"
                              checked={raw === undefined ? Boolean(spec.default) : Boolean(raw)}
                              onChange={e => setParamValues(p => ({ ...p, [key]: e.target.checked }))}
                              className="accent-purple-500 cursor-pointer"
                            />
                          ) : spec.type === 'string' ? (
                            <input
                              type="text"
                              value={raw === undefined ? String(spec.default ?? '') : String(raw)}
                              onChange={e => setParamValues(p => ({ ...p, [key]: e.target.value }))}
                              className="w-24 px-1.5 py-0.5 text-right font-mono rounded bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-purple-500"
                            />
                          ) : (
                            <input
                              type="number"
                              value={raw === undefined ? numDefault : Number(raw)}
                              min={spec.minimum}
                              max={spec.maximum}
                              step={step}
                              onChange={e => setParamValues(p => ({ ...p, [key]: Number(e.target.value) }))}
                              title={spec.minimum !== undefined ? `Range ${spec.minimum}–${spec.maximum}` : undefined}
                              className="w-20 px-1.5 py-0.5 text-right font-mono rounded bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-purple-500"
                            />
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-slate-500 mt-2">
              Edit values and click <span className="text-slate-300 font-semibold">Recompute</span> to
              re-materialize signals across the universe with your settings. Out-of-range values are clamped
              to each param's min/max. This rebuilds the shared signal table (can take a few minutes).
            </p>
          </div>
        )}
      </div>

      {/* Results table */}
      <div className="flex-1 overflow-auto rounded-xl border border-slate-800/80 bg-[#0d0f14]">
        {loading ? (
          <div className="flex items-center justify-center h-40 text-slate-500 text-sm">
            <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading signals…
          </div>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-slate-500 text-sm gap-1">
            <p>No signals for these settings.</p>
            <p className="text-[11px] text-slate-600">{counts.scanned ?? 0} symbols scanned · try lowering Min score or adding WATCH.</p>
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-[#121620] border-b border-slate-800 text-slate-400">
              <tr>
                <th className="w-6"></th>
                {([['symbol', 'Symbol'], ['score', 'Score'], ['last_close', 'Last'],
                   ['risk_pct', 'Risk %'], ['rr', 'R:R']] as [SortField, string][]).map(([f, label]) => (
                  <th key={f} onClick={() => setSort(f)}
                      className="px-3 py-2 text-left font-bold cursor-pointer hover:text-slate-200 select-none">
                    {label}{sortField === f ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
                  </th>
                ))}
                <th className="px-3 py-2 text-left font-bold">Signal</th>
                <th className="px-3 py-2 text-left font-bold">Entry</th>
                <th className="px-3 py-2 text-left font-bold">Stop</th>
                <th className="px-3 py-2 text-left font-bold">Target</th>
                <th className="px-3 py-2 text-left font-bold">Key metrics</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <React.Fragment key={r.symbol_id}>
                  <tr className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="text-center">
                      <button onClick={() => setExpanded(expanded === r.symbol_id ? null : r.symbol_id)}
                              className="text-slate-500 hover:text-slate-300">
                        {expanded === r.symbol_id ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      </button>
                    </td>
                    <td className="px-3 py-2">
                      <button onClick={() => openSymbol(r.symbol)} className="font-bold text-slate-100 hover:text-purple-400 cursor-pointer">
                        {r.symbol.replace('.NS', '')}
                      </button>
                      <div className="text-[10px] text-slate-500 truncate max-w-[160px]">{r.company_name}</div>
                    </td>
                    <td className="px-3 py-2 font-mono font-bold text-slate-200">{num(r.score, 0)}</td>
                    <td className="px-3 py-2 font-mono text-slate-300">{num(r.last_close)}</td>
                    <td className="px-3 py-2 font-mono text-slate-300">{pct(r.risk_pct)}</td>
                    <td className="px-3 py-2 font-mono text-slate-300">{r.rr === null ? '-' : `${num(r.rr)}`}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${SIGNAL_STYLE[r.signal]}`}>{SIGNAL_LABEL[r.signal as SignalKind] ?? r.signal}</span>
                    </td>
                    <td className="px-3 py-2 font-mono text-emerald-300">{num(r.entry_ref)}</td>
                    <td className="px-3 py-2 font-mono text-rose-300">{num(r.initial_stop)}</td>
                    <td className="px-3 py-2 font-mono text-sky-300">{num(r.target)}</td>
                    <td className="px-3 py-2 text-[10px] text-slate-400">
                      {Object.entries(r.key_metrics).slice(0, 4).map(([k, v]) =>
                        v === null ? null : <span key={k} className="mr-2">{k}:<span className="text-slate-200">{String(v)}</span></span>)}
                    </td>
                    <td className="px-3 py-2">
                      <button onClick={() => { const targetId = activeWatchlistId ?? watchlists[0]?.id; if (targetId) addToWatchlist(targetId, r.symbol); }}
                              title="Add to watchlist"
                              className="text-slate-500 hover:text-indigo-400 cursor-pointer">
                        <Bookmark className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                  {expanded === r.symbol_id && (
                    <tr className="bg-slate-900/40">
                      <td></td>
                      <td colSpan={11} className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5 mb-2">
                          {Object.entries(r.gates).map(([g, ok]) => (
                            <span key={g} className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              ok ? 'text-emerald-400 bg-emerald-950/30 border-emerald-800/40'
                                 : 'text-rose-400 bg-rose-950/30 border-rose-800/40'}`}>
                              {g} {ok ? '✓' : '✗'}
                            </span>
                          ))}
                        </div>
                        <ul className="text-[11px] text-slate-400 list-disc list-inside space-y-0.5">
                          {(r.reasons || []).map((reason, i) => <li key={i}>{reason}</li>)}
                        </ul>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
