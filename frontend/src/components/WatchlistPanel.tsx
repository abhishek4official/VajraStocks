import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStockStore } from '../store/useStockStore';
import { Bookmark, Plus, Trash2, Eye, X, Edit2, Check, Bell, BellOff } from 'lucide-react';
import type { AlertType } from '../store/useStockStore';

export const WatchlistPanel: React.FC = () => {
  const {
    watchlists,
    activeWatchlistId,
    screenerResults,
    alerts,
    fetchWatchlists,
    createWatchlist,
    deleteWatchlist,
    renameWatchlist,
    setActiveWatchlist,
    removeFromWatchlist,
    addAlert,
    removeAlert,
    setSelectedSymbol,
  } = useStockStore();
  const navigate = useNavigate();

  useEffect(() => { fetchWatchlists(); }, [fetchWatchlists]);

  const [alertSymbol, setAlertSymbol] = useState<string | null>(null);
  const [alertType, setAlertType] = useState<AlertType>('price_above');
  const [alertThreshold, setAlertThreshold] = useState<string>('');

  const handleAddAlert = () => {
    if (!alertSymbol || !alertThreshold) return;
    const val = parseFloat(alertThreshold);
    if (isNaN(val)) return;
    addAlert(alertSymbol, alertType, val);
    // Request notification permission if not yet granted
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
    setAlertSymbol(null);
    setAlertThreshold('');
  };

  const [newListName, setNewListName] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');

  const activeList = watchlists.find(w => w.id === activeWatchlistId) ?? watchlists[0];

  const handleCreateList = () => {
    const name = newListName.trim();
    if (!name) return;
    createWatchlist(name);
    setNewListName('');
  };

  const handleRename = (id: string) => {
    const name = editingName.trim();
    if (name) renameWatchlist(id, name);
    setEditingId(null);
  };

  const handleInspect = async (symbol: string) => {
    await setSelectedSymbol(symbol);
    navigate('/research/explorer');
  };

  // Look up latest screener snapshot data for watchlist items
  const getScreenerData = (symbol: string) =>
    screenerResults.find(r => r.symbol === symbol || r.symbol === symbol.replace('.NS', '') + '.NS');

  const pnlClass = (v: number | null | undefined) =>
    v == null ? 'text-slate-400' : v >= 0 ? 'text-emerald-400' : 'text-rose-400';

  return (
    <div className="flex-1 flex overflow-hidden max-h-full">

      {/* ── Sidebar: list tabs ─────────────────────────────────────────────── */}
      <div className="w-56 shrink-0 border-r border-border-subtle flex flex-col bg-bg-surface">
        <div className="p-4 border-b border-border-subtle">
          <h2 className="text-sm font-bold text-text-main flex items-center gap-2">
            <Bookmark className="w-4 h-4 text-accent-primary" />
            Watchlists
          </h2>
        </div>

        {/* List of watchlists */}
        <div className="flex-1 overflow-y-auto py-2">
          {watchlists.map(wl => (
      <button
        key={wl.id}
        onClick={() => setActiveWatchlist(wl.id)}
        className={`group flex items-center justify-between px-4 py-2.5 cursor-pointer transition ${
          activeList?.id === wl.id
            ? 'bg-purple-600/20 text-text-main border-r-2 border-purple-500 font-bold'
            : 'text-text-muted hover:text-text-main hover:bg-slate-900/40'
        }`}
      >
              {editingId === wl.id ? (
                <input
                  autoFocus
                  value={editingName}
                  onClick={e => e.stopPropagation()}
                  onChange={e => setEditingName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleRename(wl.id); if (e.key === 'Escape') setEditingId(null); }}
                  className="text-xs bg-bg-base border border-border-subtle rounded px-2 py-0.5 text-text-main w-full focus:outline-none focus:border-accent-primary"
                />
              ) : (
                <span className="text-xs font-semibold truncate flex-1">{wl.name}</span>
              )}

              <div className="flex items-center gap-1 ml-1 opacity-0 group-hover:opacity-100 transition shrink-0">
                {editingId === wl.id ? (
                  <button onClick={(e) => { e.stopPropagation(); handleRename(wl.id); }}
                    className="text-emerald-400 hover:text-emerald-300 cursor-pointer">
                    <Check className="w-3 h-3" />
                  </button>
                ) : (
                  <button onClick={(e) => { e.stopPropagation(); setEditingId(wl.id); setEditingName(wl.name); }}
                    className="text-text-muted hover:text-text-main cursor-pointer">
                    <Edit2 className="w-3 h-3" />
                  </button>
                )}
                {watchlists.length > 1 && (
                  <button onClick={(e) => { e.stopPropagation(); deleteWatchlist(wl.id); }}
                    className="text-slate-500 hover:text-rose-400 cursor-pointer">
                    <Trash2 className="w-3 h-3" />
                  </button>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* New list input */}
        <div className="p-3 border-t border-slate-800">
          <div className="flex gap-1.5">
            <input
              value={newListName}
              onChange={e => setNewListName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleCreateList(); }}
              placeholder="New list name..."
              className="flex-1 px-2.5 py-1.5 text-xs rounded bg-bg-base border border-border-subtle text-text-main focus:outline-none focus:border-accent-primary transition"
            />
            <button
              onClick={handleCreateList}
              disabled={!newListName.trim()}
              className="p-1.5 rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Main: watchlist items ──────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col p-5 overflow-y-auto gap-4">

        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-lg font-bold text-text-main">{activeList?.name ?? 'Watchlist'}</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {activeList?.items.length ?? 0} ticker{activeList?.items.length !== 1 ? 's' : ''}
              {' · '}Prices from last screener sweep
            </p>
          </div>
        </div>

        {!activeList || activeList.items.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-20 gap-3">
            <Bookmark className="w-12 h-12 text-slate-700" />
            <div className="text-center">
              <p className="font-semibold text-slate-400">No tickers yet</p>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Add stocks from the Screener (bookmark icon) or Explorer dashboard.
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-bg-surface/60 rounded-xl border border-border-subtle overflow-hidden">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-400 uppercase tracking-wider font-mono">
                  <th className="py-2.5 px-4">Symbol</th>
                  <th className="py-2.5 px-4 text-right">Last EOD Price</th>
                  <th className="py-2.5 px-4 text-right">Change %</th>
                  <th className="py-2.5 px-4 text-center">RSI (14)</th>
                  <th className="py-2.5 px-4 text-center">Heikin Ashi</th>
                  <th className="py-2.5 px-4 text-center">Renko</th>
                  <th className="py-2.5 px-4 text-center">SMA 200</th>
                  <th className="py-2.5 px-4 text-center">RS 1M</th>
                  <th className="py-2.5 px-4 text-center">Gap</th>
                  <th className="py-2.5 px-4 text-right">Added</th>
                  <th className="py-2.5 px-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850">
                {activeList.items.map(item => {
                  const snap = getScreenerData(item.symbol);
                  const bull = (snap?.price_pct_change ?? 0) >= 0;
                  const added = new Date(item.addedAt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });

                  return (
                    <tr key={item.symbol} className="hover:bg-slate-900/40 transition">
                      <td className="py-3 px-4 font-bold text-text-main font-mono tracking-wide">
                        {item.symbol.replace('.NS', '')}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-text-main">
                        {snap ? `₹${snap.close_price.toFixed(2)}` : '—'}
                      </td>
                      <td className={`py-3 px-4 text-right font-mono font-semibold ${pnlClass(snap?.price_pct_change)}`}>
                        {snap?.price_pct_change != null
                          ? `${bull ? '+' : ''}${snap.price_pct_change.toFixed(2)}%`
                          : '—'}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {snap?.rsi_14 != null ? (
                          <span className={`font-mono text-xs px-2 py-0.5 rounded border ${
                            snap.rsi_14 >= 70 ? 'text-rose-400 bg-rose-950/20 border-rose-900/30'
                            : snap.rsi_14 <= 30 ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30'
                            : 'text-slate-300 bg-slate-900/50 border-slate-800'
                          }`}>
                            {snap.rsi_14.toFixed(1)}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {snap ? (
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            snap.ha_direction === 'UP' ? 'text-emerald-400 bg-emerald-950/25' : 'text-rose-400 bg-rose-950/25'
                          }`}>
                            {snap.ha_direction}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {snap?.renko_direction ? (
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            snap.renko_direction === 'UP' ? 'text-emerald-400 bg-emerald-950/25' : 'text-rose-400 bg-rose-950/25'
                          }`}>
                            {snap.renko_direction}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {snap?.sma_200_cross_direction ? (
                          <span className={`text-xs px-2 py-0.5 rounded border ${
                            snap.sma_200_cross_direction === 'ABOVE'
                              ? 'text-indigo-400 bg-indigo-950/20 border-indigo-900/30'
                              : 'text-amber-400 bg-amber-950/20 border-amber-900/30'
                          }`}>
                            {snap.sma_200_cross_direction}
                          </span>
                        ) : '—'}
                      </td>
                      {/* RS Score */}
                      <td className="py-3 px-4 text-center">
                        {snap?.rs_score_1m != null ? (
                          <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
                            snap.rs_score_1m >= 1.2 ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30'
                            : snap.rs_score_1m >= 0.8 ? 'text-slate-300 bg-slate-900/40 border-slate-800'
                            : 'text-rose-400 bg-rose-950/20 border-rose-900/30'
                          }`}>
                            {snap.rs_score_1m.toFixed(2)}x
                          </span>
                        ) : '—'}
                      </td>
                      {/* Gap */}
                      <td className="py-3 px-4 text-center">
                        {snap?.is_gap_up   && <span className="text-[10px] font-bold text-emerald-400 bg-emerald-950/20 border border-emerald-900/30 px-1.5 py-0.5 rounded">GAP ↑</span>}
                        {snap?.is_gap_down && <span className="text-[10px] font-bold text-rose-400 bg-rose-950/20 border border-rose-900/30 px-1.5 py-0.5 rounded">GAP ↓</span>}
                        {!snap?.is_gap_up && !snap?.is_gap_down && <span className="text-slate-600">—</span>}
                      </td>
                      <td className="py-3 px-4 text-right text-xs text-slate-500 font-mono">{added}</td>
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center gap-1.5 justify-center">
                          <button
                            onClick={() => handleInspect(item.symbol)}
                            className="p-1 px-2 rounded bg-slate-900 border border-slate-800 hover:border-purple-500/80 text-slate-400 hover:text-text-main text-xs flex items-center gap-1 transition cursor-pointer"
                          >
                            <Eye className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => { setAlertSymbol(item.symbol); setAlertThreshold(snap?.close_price?.toFixed(2) ?? ''); }}
                            title="Set alert"
                            className="p-1 px-2 rounded bg-slate-900 border border-slate-800 hover:border-amber-500/80 text-slate-500 hover:text-amber-400 text-xs flex items-center transition cursor-pointer"
                          >
                            <Bell className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => activeList && removeFromWatchlist(activeList.id, item.symbol)}
                            className="p-1 px-2 rounded bg-slate-900 border border-slate-800 hover:border-rose-500/80 text-slate-500 hover:text-rose-400 text-xs flex items-center transition cursor-pointer"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Alert creation form (inline popup) ───────────────────────── */}
        {alertSymbol && (
          <div className="p-4 rounded-xl border border-amber-900/40 bg-amber-950/10">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
                <Bell className="w-3.5 h-3.5" />
                Set Alert — {alertSymbol.replace('.NS', '')}
              </h4>
              <button onClick={() => setAlertSymbol(null)} className="text-slate-500 hover:text-text-main cursor-pointer">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="flex gap-2 flex-wrap">
              <select
                value={alertType}
                onChange={e => setAlertType(e.target.value as AlertType)}
                className="px-2 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-text-main focus:outline-none focus:border-amber-500"
              >
                <option value="price_above">Price rises above ₹</option>
                <option value="price_below">Price falls below ₹</option>
                <option value="rsi_above">RSI rises above</option>
                <option value="rsi_below">RSI falls below</option>
              </select>
              <input
                type="number"
                value={alertThreshold}
                onChange={e => setAlertThreshold(e.target.value)}
                placeholder="threshold"
                className="w-28 px-2 py-1.5 text-xs rounded bg-slate-900 border border-slate-800 text-text-main focus:outline-none focus:border-amber-500 font-mono"
              />
              <button
                onClick={handleAddAlert}
                disabled={!alertThreshold}
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white rounded text-xs font-bold cursor-pointer transition"
              >
                Set Alert
              </button>
            </div>
          </div>
        )}

        {/* ── Active alerts list ────────────────────────────────────────── */}
        {alerts.length > 0 && (
          <div className="p-4 rounded-xl border border-border-subtle bg-bg-surface/30">
            <h4 className="text-xs font-bold text-slate-300 flex items-center gap-1.5 mb-3">
              <Bell className="w-3.5 h-3.5 text-amber-400" />
              Active Alerts ({alerts.filter(a => !a.triggered).length} pending · {alerts.filter(a => a.triggered).length} fired)
            </h4>
            <div className="space-y-1.5">
              {alerts.map(a => (
                <div key={a.id} className={`flex items-center justify-between px-3 py-2 rounded-lg border text-xs ${
                  a.triggered
                    ? 'border-emerald-900/40 bg-emerald-950/10 text-emerald-400'
                    : 'border-slate-800 bg-slate-900/40 text-slate-300'
                }`}>
                  <span className="font-mono font-bold">{a.symbol.replace('.NS', '')}</span>
                  <span className="text-slate-400">{a.type.replace('_', ' ')} {a.type.startsWith('rsi') ? '' : '₹'}{a.threshold}</span>
                  <span>{a.triggered ? '✅ Fired' : '⏳ Watching'}</span>
                  <button onClick={() => removeAlert(a.id)} className="text-slate-600 hover:text-rose-400 cursor-pointer">
                    <BellOff className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
