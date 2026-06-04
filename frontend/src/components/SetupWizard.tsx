import React, { useEffect, useState } from 'react';
import { Database, Cpu, Download, CheckCircle, ChevronRight, Loader2, LineChart } from 'lucide-react';

const BASE = `${import.meta.env.VITE_API_BASE_URL}/api/v1`;

type Step = 'ai' | 'database' | 'symbols' | 'done';

const STEPS: { id: Step; label: string; Icon: React.FC<{ className?: string }> }[] = [
  { id: 'ai',       label: 'AI Provider',      Icon: Cpu      },
  { id: 'database', label: 'Database',          Icon: Database },
  { id: 'symbols',  label: 'Download Symbols',  Icon: Download },
  { id: 'done',     label: 'Launch',            Icon: CheckCircle },
];

export const SetupWizard: React.FC<{ onComplete: () => void }> = ({ onComplete }) => {
  const [step, setStep] = useState<Step>('ai');
  const [aiProvider, setAiProvider] = useState('ollama');
  const [aiBaseUrl, setAiBaseUrl] = useState('http://localhost:11434');
  const [aiModel, setAiModel] = useState('qwen2.5-coder:7b');
  const [aiApiKey, setAiApiKey] = useState('');
  const [dbProvider, setDbProvider] = useState('sqlite');
  const [dbPath, setDbPath] = useState('data/vajra.db');
  const [downloadSymbols, setDownloadSymbols] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-populate from existing DB settings so re-runs show current values
  useEffect(() => {
    fetch(`${BASE}/settings`)
      .then(r => r.ok ? r.json() : null)
      .then((data: Record<string, Array<{ key: string; value: string }>> | null) => {
        if (!data) return;
        const ai = (k: string) => data['AI']?.find(s => s.key === k)?.value;
        const db = (k: string) => data['DATABASE']?.find(s => s.key === k)?.value;
        if (ai('ai_provider')) setAiProvider(ai('ai_provider')!);
        if (ai('ai_base_url')) setAiBaseUrl(ai('ai_base_url')!);
        if (ai('ai_model'))    setAiModel(ai('ai_model')!);
        if (db('db_provider')) setDbProvider(db('db_provider')!);
        const connStr = db('db_connection_string') ?? '';
        // Strip sqlite:/// prefix for display in the path field
        if (connStr.startsWith('sqlite:///')) setDbPath(connStr.replace('sqlite:///', ''));
        else if (connStr) setDbPath(connStr);
      })
      .catch(() => { /* keep hardcoded defaults if settings unavailable */ });
  }, []);

  const currentIdx = STEPS.findIndex(s => s.id === step);

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const connStr = dbProvider === 'sqlite'
        ? `sqlite:///${dbPath}`
        : dbPath; // for PG/MSSQL the user pastes a full URL

      const res = await fetch(`${BASE}/setup/initialize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          db_provider: dbProvider,
          db_connection_string: connStr,
          ai_provider: aiProvider,
          ai_base_url: aiBaseUrl,
          ai_model: aiModel,
          ai_api_key: aiApiKey,
          download_symbols: downloadSymbols,
        }),
      });
      if (!res.ok) throw new Error('Setup failed — check the server logs.');
      setStep('done');
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#07080a] flex items-center justify-center p-6">
      <div className="w-full max-w-lg">

        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="p-2.5 bg-purple-600/10 border border-purple-500/30 rounded-xl text-purple-400">
            <LineChart className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">
              VAJRA <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-mono">STOCKS</span>
            </h1>
            <p className="text-[10px] text-slate-400">First-run setup</p>
          </div>
        </div>

        {/* Step indicator */}
        <div className="flex items-center justify-center gap-1 mb-8">
          {STEPS.map((s, i) => (
            <React.Fragment key={s.id}>
              <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                s.id === step
                  ? 'bg-purple-600 text-white'
                  : i < currentIdx
                  ? 'text-emerald-400 bg-emerald-950/20'
                  : 'text-slate-500'
              }`}>
                <s.Icon className="w-3.5 h-3.5" />
                {s.label}
              </div>
              {i < STEPS.length - 1 && <ChevronRight className="w-3.5 h-3.5 text-slate-700 shrink-0" />}
            </React.Fragment>
          ))}
        </div>

        {/* Step content */}
        <div className="bg-[#0d0f14] rounded-2xl border border-slate-800 p-6 flex flex-col gap-5">

          {/* AI Provider Step */}
          {step === 'ai' && (
            <>
              <h2 className="text-lg font-bold text-white">Configure AI Provider</h2>
              <p className="text-xs text-slate-400">
                VajraStocks uses a local Ollama instance by default — no cloud account needed.
              </p>
              <div className="flex gap-2">
                {['ollama', 'openai'].map(p => (
                  <button key={p} onClick={() => setAiProvider(p)}
                    className={`flex-1 py-2 rounded-lg border text-sm font-bold transition cursor-pointer ${
                      aiProvider === p ? 'border-purple-500 bg-purple-600/20 text-white' : 'border-slate-800 text-slate-400 hover:text-white'
                    }`}>
                    {p === 'ollama' ? '🦙 Ollama (local)' : '☁️ OpenAI-compatible'}
                  </button>
                ))}
              </div>
              <Field label="Provider Base URL" value={aiBaseUrl} onChange={setAiBaseUrl} placeholder="http://localhost:11434" />
              <Field label="Model Name" value={aiModel} onChange={setAiModel} placeholder="qwen2.5-coder:7b" />
              {aiProvider !== 'ollama' && (
                <Field label="API Key" value={aiApiKey} onChange={setAiApiKey} placeholder="sk-..." type="password" />
              )}
              <Next onClick={() => setStep('database')} />
            </>
          )}

          {/* Database Step */}
          {step === 'database' && (
            <>
              <h2 className="text-lg font-bold text-white">Database</h2>
              <p className="text-xs text-slate-400">SQLite is recommended for single-user local installs.</p>
              <div className="flex gap-2">
                {[
                  { id: 'sqlite', label: '🗃️ SQLite (default)' },
                  { id: 'postgresql', label: '🐘 PostgreSQL' },
                  { id: 'mssql', label: '🪟 MSSQL LocalDB' },
                ].map(opt => (
                  <button key={opt.id} onClick={() => setDbProvider(opt.id)}
                    className={`flex-1 py-2 rounded-lg border text-xs font-bold transition cursor-pointer ${
                      dbProvider === opt.id ? 'border-purple-500 bg-purple-600/20 text-white' : 'border-slate-800 text-slate-400 hover:text-white'
                    }`}>
                    {opt.label}
                  </button>
                ))}
              </div>
              {dbProvider === 'sqlite' ? (
                <Field label="Database file path" value={dbPath} onChange={setDbPath} placeholder="data/vajra.db" />
              ) : (
                <Field label="Connection string" value={dbPath} onChange={setDbPath}
                  placeholder={dbProvider === 'postgresql' ? 'postgresql+psycopg2://user:pass@localhost/vajra' : 'mssql+pyodbc://...'} />
              )}
              <div className="flex gap-2">
                <Back onClick={() => setStep('ai')} />
                <Next onClick={() => setStep('symbols')} />
              </div>
            </>
          )}

          {/* Symbol Download Step */}
          {step === 'symbols' && (
            <>
              <h2 className="text-lg font-bold text-white">Download NSE Symbols</h2>
              <p className="text-xs text-slate-400">
                Downloads 2,300+ NSE equity symbols from NSE India. This runs in the background after setup — you can start using the app immediately.
              </p>
              <label className="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-slate-800 hover:bg-slate-900/40 transition">
                <input type="checkbox" checked={downloadSymbols} onChange={e => setDownloadSymbols(e.target.checked)} className="accent-purple-500 w-4 h-4" />
                <div>
                  <p className="text-sm font-semibold text-white">Auto-download NSE symbols</p>
                  <p className="text-[10px] text-slate-500">Recommended — takes 1–2 minutes in the background</p>
                </div>
              </label>
              {error && <div className="p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 text-rose-400 text-xs">{error}</div>}
              <div className="flex gap-2">
                <Back onClick={() => setStep('database')} />
                <button
                  onClick={submit}
                  disabled={loading}
                  className="flex-1 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg text-sm font-bold transition cursor-pointer flex items-center justify-center gap-2"
                >
                  {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Initialising…</> : '🚀 Complete Setup'}
                </button>
              </div>
            </>
          )}

          {/* Done */}
          {step === 'done' && (
            <div className="text-center py-4 flex flex-col items-center gap-4">
              <CheckCircle className="w-12 h-12 text-emerald-400" />
              <h2 className="text-xl font-bold text-white">Setup Complete!</h2>
              <p className="text-sm text-slate-400">
                {downloadSymbols
                  ? 'Symbol download is running in the background. The dashboard is ready to use now — symbols will appear as they sync.'
                  : 'VajraStocks is ready. You can download symbols later from the Sync Centre.'}
              </p>
              <button
                onClick={onComplete}
                className="mt-2 px-8 py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-xl font-bold text-sm transition cursor-pointer"
              >
                Open Dashboard →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ── Reusable mini-components ──────────────────────────────────────────────────

const Field: React.FC<{ label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string }> = ({ label, value, onChange, placeholder, type = 'text' }) => (
  <div className="flex flex-col gap-1.5">
    <label className="text-xs font-semibold text-slate-400">{label}</label>
    <input
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="px-3 py-2 text-sm rounded-lg bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500 transition font-mono"
    />
  </div>
);

const Next: React.FC<{ onClick: () => void; label?: string }> = ({ onClick, label = 'Next →' }) => (
  <button onClick={onClick} className="w-full py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-sm font-bold transition cursor-pointer">
    {label}
  </button>
);

const Back: React.FC<{ onClick: () => void }> = ({ onClick }) => (
  <button onClick={onClick} className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-bold transition cursor-pointer">
    ← Back
  </button>
);
