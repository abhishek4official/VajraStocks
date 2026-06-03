import React, { useEffect, useState } from 'react';
import { Settings, Save, Eye, EyeOff, RefreshCw, CheckCircle } from 'lucide-react';

interface Setting {
  id: number;
  category: string;
  key: string;
  value: string;
  value_type: string;
  description: string | null;
  is_secret: boolean;
}

type SettingsByCategory = Record<string, Setting[]>;

const BASE = `${import.meta.env.VITE_API_BASE_URL}/api/v1`;

const CATEGORY_LABELS: Record<string, string> = {
  AI:          '🤖 AI Provider',
  DATABASE:    '🗄️ Database',
  DOWNLOADER:  '📥 Data Downloader',
  MARKET:      '📊 Market',
  APPLICATION: '⚙️ Application',
};

export const SettingsPanel: React.FC = () => {
  const [settings, setSettings] = useState<SettingsByCategory>({});
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [saved, setSaved] = useState<Record<string, boolean>>({});
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/settings`);
      if (!res.ok) throw new Error('Failed to load settings');
      const data: SettingsByCategory = await res.json();
      setSettings(data);
      setEdits({});
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const key = (s: Setting) => `${s.category}/${s.key}`;

  const handleChange = (s: Setting, val: string) => {
    setEdits(prev => ({ ...prev, [key(s)]: val }));
    setSaved(prev => ({ ...prev, [key(s)]: false }));
  };

  const handleSave = async (s: Setting) => {
    const k = key(s);
    const value = edits[k] ?? s.value;
    setSaving(prev => ({ ...prev, [k]: true }));
    try {
      const res = await fetch(`${BASE}/settings/${s.category}/${s.key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      });
      if (!res.ok) throw new Error('Save failed');
      setSaved(prev => ({ ...prev, [k]: true }));
      // update local cache
      setSettings(prev => ({
        ...prev,
        [s.category]: prev[s.category].map(x => x.key === s.key ? { ...x, value } : x),
      }));
      setTimeout(() => setSaved(prev => ({ ...prev, [k]: false })), 2000);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSaving(prev => ({ ...prev, [k]: false }));
    }
  };

  const categoryOrder = ['AI', 'DATABASE', 'DOWNLOADER', 'MARKET', 'APPLICATION'];

  if (loading) return (
    <div className="flex-1 flex items-center justify-center text-slate-500">
      <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading settings…
    </div>
  );

  return (
    <div className="flex-1 flex flex-col gap-5 p-5 overflow-y-auto max-h-full">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-purple-500" /> Application Settings
          </h2>
          <p className="text-xs text-slate-400 mt-1">All settings are stored in the database and take effect immediately.</p>
        </div>
        <button onClick={load} className="p-2 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition cursor-pointer">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 text-rose-400 text-xs">{error}</div>
      )}

      {categoryOrder.filter(c => settings[c]?.length).map(category => (
        <div key={category} className="rounded-xl border border-slate-800/80 bg-[#121620]/30 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 bg-slate-900/40">
            <h3 className="text-sm font-bold text-white">{CATEGORY_LABELS[category] ?? category}</h3>
          </div>
          <div className="divide-y divide-slate-800/50">
            {settings[category].map(s => {
              const k = key(s);
              const currentVal = edits[k] ?? s.value;
              const isDirty = edits[k] !== undefined && edits[k] !== s.value;
              const isSecret = s.is_secret;
              const revealed = showSecret[k];

              return (
                <div key={k} className="flex items-start gap-4 px-4 py-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-semibold text-slate-300">{s.key}</span>
                      {isSecret && <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/30 border border-amber-900/40 text-amber-500">SECRET</span>}
                    </div>
                    {s.description && <p className="text-[10px] text-slate-500 mt-0.5">{s.description}</p>}
                  </div>
                  <div className="flex items-center gap-2 shrink-0 w-72">
                    <div className="relative flex-1">
                      <input
                        type={isSecret && !revealed ? 'password' : 'text'}
                        value={currentVal}
                        onChange={e => handleChange(s, e.target.value)}
                        className={`w-full px-3 py-1.5 text-xs rounded-lg bg-slate-900 border text-white focus:outline-none transition font-mono ${
                          isDirty ? 'border-purple-500/60' : 'border-slate-800 focus:border-purple-500'
                        }`}
                      />
                      {isSecret && (
                        <button
                          onClick={() => setShowSecret(prev => ({ ...prev, [k]: !revealed }))}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white cursor-pointer"
                        >
                          {revealed ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      )}
                    </div>
                    <button
                      onClick={() => handleSave(s)}
                      disabled={!isDirty || saving[k]}
                      className={`p-1.5 rounded-lg border transition cursor-pointer ${
                        saved[k]
                          ? 'border-emerald-900/40 bg-emerald-950/20 text-emerald-400'
                          : isDirty
                          ? 'border-purple-500/60 bg-purple-600/20 text-purple-400 hover:bg-purple-600/40'
                          : 'border-slate-800 text-slate-600 opacity-40 cursor-not-allowed'
                      }`}
                    >
                      {saved[k] ? <CheckCircle className="w-3.5 h-3.5" /> : saving[k] ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
