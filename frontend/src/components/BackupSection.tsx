import { useRef, useState } from 'react';
import { Download, Upload, ShieldCheck } from 'lucide-react';
import { apiService } from '../services/api';

export function BackupSection() {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const doExport = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const data = await apiService.exportBackup();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `vajra-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      const t = (data.journal_trades as unknown[] | undefined)?.length ?? 0;
      setMsg(`Exported ${t} journal trade(s) + watchlists & notes.`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Export failed');
    } finally {
      setBusy(false);
    }
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setMsg(null);
    try {
      const data = JSON.parse(await file.text());
      const c = await apiService.importBackup(data);
      setMsg(`Imported — ${c.journal_trades} trades, ${c.watchlist_items} watchlist items, ${c.swing_pick_notes} notes added.`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <div className="mt-3 rounded-xl border border-border-subtle bg-bg-surface/60 p-4">
      <div className="flex items-center gap-2 mb-1">
        <ShieldCheck className="w-4 h-4 text-accent-primary" />
        <h3 className="text-sm font-bold text-text-main">Backup & Restore</h3>
      </div>
      <p className="text-[11px] text-text-muted mb-3">
        Export your irreplaceable data (trade journal, watchlists, pick notes) to a portable JSON file.
        Price data is re-syncable and not included. Import is idempotent.
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={doExport} disabled={busy}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent-primary text-accent-text text-xs font-bold disabled:opacity-50 cursor-pointer">
          <Download className="w-3.5 h-3.5" /> Export
        </button>
        <button onClick={() => fileRef.current?.click()} disabled={busy}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border-subtle text-text-muted hover:text-text-main text-xs disabled:opacity-50 cursor-pointer">
          <Upload className="w-3.5 h-3.5" /> Import
        </button>
        <input ref={fileRef} type="file" accept="application/json" className="hidden" onChange={onFile} />
        {msg && <span className="text-[11px] text-text-muted">{msg}</span>}
      </div>
    </div>
  );
}
