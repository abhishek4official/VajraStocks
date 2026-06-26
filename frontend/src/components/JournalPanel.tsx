import { useEffect, useState } from 'react';
import { BookMarked, Plus, Trash2, BarChart3 } from 'lucide-react';
import { apiService, type JournalTrade, type SetupStats } from '../services/api';

const PCT = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(2)}%`;
const NUM = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined ? '—' : v.toFixed(d);
const today = () => new Date().toISOString().slice(0, 10);

const blankForm = {
  symbol: '', setup: 'pullback', side: 'LONG',
  entry_date: today(), entry_price: '', qty: '', stop_price: '', target_price: '', thesis: '',
};

export function JournalPanel() {
  const [trades, setTrades] = useState<JournalTrade[]>([]);
  const [review, setReview] = useState<SetupStats[]>([]);
  const [form, setForm] = useState({ ...blankForm });
  const [exitDraft, setExitDraft] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    apiService.listTrades().then(setTrades).catch(() => setTrades([]));
    apiService.journalReview().then(setReview).catch(() => setReview([]));
  };
  useEffect(() => { refresh(); }, []);

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const log = async () => {
    setError(null);
    try {
      await apiService.logTrade({
        symbol: form.symbol, setup: form.setup, side: form.side,
        entry_date: form.entry_date, entry_price: Number(form.entry_price), qty: Number(form.qty),
        stop_price: form.stop_price ? Number(form.stop_price) : null,
        target_price: form.target_price ? Number(form.target_price) : null,
        thesis: form.thesis || null,
      });
      setForm({ ...blankForm });
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to log trade');
    }
  };

  const close = async (t: JournalTrade) => {
    const price = Number(exitDraft[t.id]);
    if (!price) return;
    await apiService.closeTrade(t.id, today(), price);
    setExitDraft(d => ({ ...d, [t.id]: '' }));
    refresh();
  };

  const remove = async (id: number) => { await apiService.deleteTrade(id); refresh(); };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-5">
      <div className="flex items-center gap-2">
        <BookMarked className="w-5 h-5 text-accent-primary" />
        <h2 className="text-lg font-bold text-text-main">Trade Journal</h2>
        <span className="text-[11px] text-text-muted">Log trades, track realized P&amp;L and R, review by setup</span>
      </div>

      {/* Log form */}
      <div className="rounded-xl border border-border-subtle bg-bg-surface/60 p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        {([
          ['symbol', 'Symbol', 'text'], ['setup', 'Setup', 'text'],
          ['entry_date', 'Entry date', 'date'], ['entry_price', 'Entry price', 'number'],
          ['qty', 'Qty', 'number'], ['stop_price', 'Stop', 'number'], ['target_price', 'Target', 'number'],
        ] as const).map(([k, label, type]) => (
          <label key={k} className="flex flex-col gap-1 text-[11px] text-text-muted">
            {label}
            <input
              type={type}
              value={(form as Record<string, string>)[k]}
              onChange={e => set(k, type === 'text' ? e.target.value.toUpperCase() : e.target.value)}
              className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-sm text-text-main"
            />
          </label>
        ))}
        <label className="flex flex-col gap-1 text-[11px] text-text-muted">
          Side
          <select value={form.side} onChange={e => set('side', e.target.value)}
            className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-sm text-text-main">
            <option>LONG</option><option>SHORT</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-text-muted md:col-span-4">
          Thesis
          <input value={form.thesis} onChange={e => set('thesis', e.target.value)}
            className="bg-bg-base border border-border-subtle rounded px-2 py-1.5 text-sm text-text-main" />
        </label>
      </div>
      <button onClick={log} disabled={!form.symbol || !form.entry_price || !form.qty}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-primary text-accent-text text-sm font-bold disabled:opacity-50 cursor-pointer">
        <Plus className="w-4 h-4" /> Log trade
      </button>
      {error && <div className="text-sm text-rose-400">{error}</div>}

      {/* Review by setup */}
      {review.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-text-main">
            <BarChart3 className="w-4 h-4" /> Review by setup
          </div>
          <div className="rounded-xl border border-border-subtle bg-bg-surface/60 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="text-text-muted border-b border-border-subtle">
                <tr>
                  <th className="text-left px-3 py-2">Setup</th><th className="text-right px-3 py-2">Trades</th>
                  <th className="text-right px-3 py-2">Win rate</th><th className="text-right px-3 py-2">Avg R</th>
                  <th className="text-right px-3 py-2">Expectancy (R)</th><th className="text-right px-3 py-2">Total P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {review.map(s => (
                  <tr key={s.setup} className="border-b border-border-subtle/50">
                    <td className="px-3 py-1.5 font-semibold text-text-main">{s.setup}</td>
                    <td className="px-3 py-1.5 text-right">{s.trades}</td>
                    <td className="px-3 py-1.5 text-right">{PCT(s.win_rate)}</td>
                    <td className="px-3 py-1.5 text-right">{NUM(s.avg_r)}</td>
                    <td className={`px-3 py-1.5 text-right font-semibold ${s.expectancy_r >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{NUM(s.expectancy_r)}</td>
                    <td className={`px-3 py-1.5 text-right ${s.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{NUM(s.total_pnl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trades */}
      <div className="space-y-2">
        <div className="text-sm font-semibold text-text-main">Trades ({trades.length})</div>
        {trades.length === 0 ? (
          <p className="text-xs text-text-muted">No trades logged yet.</p>
        ) : (
          <div className="rounded-xl border border-border-subtle bg-bg-surface/60 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="text-text-muted border-b border-border-subtle">
                <tr>
                  <th className="text-left px-3 py-2">Symbol</th><th className="text-left px-3 py-2">Setup</th>
                  <th className="text-left px-3 py-2">Status</th><th className="text-right px-3 py-2">Entry</th>
                  <th className="text-right px-3 py-2">Exit</th><th className="text-right px-3 py-2">P&amp;L</th>
                  <th className="text-right px-3 py-2">R</th><th className="text-right px-3 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <tr key={t.id} className="border-b border-border-subtle/50">
                    <td className="px-3 py-1.5 font-semibold">{t.symbol.replace('.NS', '')}</td>
                    <td className="px-3 py-1.5 text-text-muted">{t.setup || '—'}</td>
                    <td className="px-3 py-1.5">{t.status}</td>
                    <td className="px-3 py-1.5 text-right">{NUM(t.entry_price)}</td>
                    <td className="px-3 py-1.5 text-right">{NUM(t.exit_price)}</td>
                    <td className={`px-3 py-1.5 text-right ${(t.pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{NUM(t.pnl)}</td>
                    <td className="px-3 py-1.5 text-right">{NUM(t.r_multiple)}</td>
                    <td className="px-3 py-1.5 text-right">
                      {t.status === 'OPEN' ? (
                        <span className="inline-flex items-center gap-1">
                          <input type="number" placeholder="exit" value={exitDraft[t.id] ?? ''}
                            onChange={e => setExitDraft(d => ({ ...d, [t.id]: e.target.value }))}
                            className="w-16 bg-bg-base border border-border-subtle rounded px-1 py-0.5 text-xs" />
                          <button onClick={() => close(t)} className="text-accent-primary font-semibold cursor-pointer">Close</button>
                        </span>
                      ) : (
                        <button onClick={() => remove(t.id)} title="Delete" className="text-slate-500 hover:text-rose-400 cursor-pointer">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
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
