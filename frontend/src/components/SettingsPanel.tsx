import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle, CheckCircle, Eye, EyeOff,
  Power, RefreshCw, RotateCcw, Save, Settings, Wifi, WifiOff,
} from 'lucide-react';
import { invalidateSettingsCache } from '../hooks/useSettings';
import { API_BASE, API_ROOT } from '../lib/apiBase';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Setting {
  id: number;
  category: string;
  key: string;
  value: string;
  value_type: 'string' | 'integer' | 'float' | 'boolean' | 'json';
  description: string | null;
  is_secret: boolean;
}

type SettingsByCategory = Record<string, Setting[]>;

interface CategoryMeta {
  category: string;
  label: string;
  count: number;
  has_restart_required: boolean;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const BASE = API_BASE;

const RESTART_REQUIRED = new Set<string>([
  'DATABASE/db_connection_string', 'DATABASE/db_provider',
  'DATABASE/db_pool_size', 'DATABASE/db_max_overflow', 'DATABASE/db_pool_recycle',
  'AI/ai_provider', 'AI/ai_base_url', 'AI/ai_model',
  'APPLICATION/log_level_console', 'APPLICATION/log_level_file', 'APPLICATION/log_file_path',
]);

const CATEGORY_ICONS: Record<string, string> = {
  AI: '🤖', DATABASE: '🗄️', DOWNLOADER: '📥',
  MARKET: '📊', SCREENER: '🔍', PORTFOLIO: '💼',
  UI: '🖥️', APPLICATION: '⚙️',
};

const RECONNECT_POLL_MS = 2000;
const RECONNECT_TIMEOUT = 30_000;

// ─── Type-aware input ─────────────────────────────────────────────────────────

const SettingInput: React.FC<{
  s: Setting;
  value: string;
  revealed: boolean;
  onChange: (v: string) => void;
  onToggleReveal: () => void;
}> = ({ s, value, revealed, onChange, onToggleReveal }) => {
  const base = 'w-full px-3 py-1.5 text-xs rounded-lg bg-slate-900 border text-white focus:outline-none transition font-mono';

  if (s.value_type === 'boolean') {
    const on = ['true', '1', 'yes'].includes(value.toLowerCase());
    return (
      <button
        type="button"
        onClick={() => onChange(on ? 'false' : 'true')}
        className={`relative w-10 h-5 rounded-full transition-colors cursor-pointer flex-shrink-0 ${
          on ? 'bg-purple-600' : 'bg-slate-700'
        }`}
      >
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
          on ? 'translate-x-5' : 'translate-x-0'
        }`} />
      </button>
    );
  }

  if (s.value_type === 'integer') {
    return (
      <input
        type="number"
        step="1"
        value={value}
        onChange={e => onChange(e.target.value)}
        className={`${base} border-slate-800 focus:border-purple-500`}
      />
    );
  }

  if (s.value_type === 'float') {
    return (
      <input
        type="number"
        step="0.01"
        value={value}
        onChange={e => onChange(e.target.value)}
        className={`${base} border-slate-800 focus:border-purple-500`}
      />
    );
  }

  // string / json / secret
  return (
    <div className="relative flex-1">
      <input
        type={s.is_secret && !revealed ? 'password' : 'text'}
        value={value}
        onChange={e => onChange(e.target.value)}
        className={`${base} border-slate-800 focus:border-purple-500 ${s.is_secret ? 'pr-8' : ''}`}
      />
      {s.is_secret && (
        <button
          type="button"
          onClick={onToggleReveal}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white cursor-pointer"
        >
          {revealed ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
        </button>
      )}
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────

export const SettingsPanel: React.FC = () => {
  const [settings, setSettings]         = useState<SettingsByCategory>({});
  const [categories, setCategories]     = useState<CategoryMeta[]>([]);
  const [activeCategory, setActiveCat]  = useState<string>('AI');
  const [edits, setEdits]               = useState<Record<string, string>>({});
  const [saving, setSaving]             = useState<Record<string, boolean>>({});
  const [saved, setSaved]               = useState<Record<string, boolean>>({});
  const [showSecret, setShowSecret]     = useState<Record<string, boolean>>({});
  const [loading, setLoading]           = useState(true);
  const [resetting, setResetting]       = useState(false);
  const [error, setError]               = useState<string | null>(null);

  const [needsRestart, setNeedsRestart]           = useState(false);
  const [restarting, setRestarting]               = useState(false);
  const [reconnecting, setReconnecting]           = useState(false);
  const [reconnectFailed, setReconnectFailed]     = useState(false);
  const [restartDone, setRestartDone]             = useState(false);
  const reconnectTimer  = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectDead   = useRef(0);

  // ── Load ────────────────────────────────────────────────────────────────────

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const [settingsRes, catRes] = await Promise.all([
        fetch(`${BASE}/settings`),
        fetch(`${BASE}/settings/categories`),
      ]);
      if (!settingsRes.ok || !catRes.ok) throw new Error('Failed to load settings');
      const [data, cats]: [SettingsByCategory, CategoryMeta[]] = await Promise.all([
        settingsRes.json(), catRes.json(),
      ]);
      setSettings(data);
      setCategories(cats);
      setEdits({});
      if (cats.length && !cats.find(c => c.category === activeCategory)) {
        setActiveCat(cats[0].category);
      }
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // ── Helpers ─────────────────────────────────────────────────────────────────

  const sk = (s: Setting) => `${s.category}/${s.key}`;

  const handleChange = (s: Setting, val: string) => {
    setEdits(p => ({ ...p, [sk(s)]: val }));
    setSaved(p => ({ ...p, [sk(s)]: false }));
  };

  // ── Save ────────────────────────────────────────────────────────────────────

  const handleSave = async (s: Setting) => {
    const k = sk(s);
    const value = edits[k] ?? s.value;
    setSaving(p => ({ ...p, [k]: true }));
    try {
      const res = await fetch(`${BASE}/settings/${s.category}/${s.key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      });
      if (!res.ok) throw new Error('Save failed');
      const data = await res.json();
      setSaved(p => ({ ...p, [k]: true }));
      setSettings(p => ({
        ...p,
        [s.category]: p[s.category].map(x => x.key === s.key ? { ...x, value } : x),
      }));
      if (data.restart_required || RESTART_REQUIRED.has(k)) setNeedsRestart(true);
      setTimeout(() => setSaved(p => ({ ...p, [k]: false })), 2000);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSaving(p => ({ ...p, [k]: false }));
    }
  };

  // ── Reset category ──────────────────────────────────────────────────────────

  const handleReset = async () => {
    if (!window.confirm(`Reset all ${activeCategory} settings to defaults?`)) return;
    setResetting(true);
    try {
      const res = await fetch(`${BASE}/settings/reset/${activeCategory}`, { method: 'POST' });
      if (!res.ok) throw new Error('Reset failed');
      const data = await res.json();
      if (data.restart_required) setNeedsRestart(true);
      await load();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setResetting(false);
    }
  };

  // ── Restart ─────────────────────────────────────────────────────────────────

  const pollHealth = () => {
    if (reconnectTimer.current) clearInterval(reconnectTimer.current);
    reconnectTimer.current = setInterval(async () => {
      if (Date.now() > reconnectDead.current) {
        clearInterval(reconnectTimer.current!);
        setReconnecting(false); setReconnectFailed(true);
        return;
      }
      try {
        const r = await fetch(`${API_ROOT}/health`, {
          signal: AbortSignal.timeout(1500),
        });
        if (r.ok) {
          clearInterval(reconnectTimer.current!);
          setReconnecting(false); setNeedsRestart(false);
          setRestartDone(true);
          invalidateSettingsCache();
          await load();
          setTimeout(() => setRestartDone(false), 4000);
        }
      } catch { /* still down */ }
    }, RECONNECT_POLL_MS);
  };

  const handleRestart = async () => {
    setRestarting(true); setReconnectFailed(false);
    try { await fetch(`${BASE}/settings/restart`, { method: 'POST' }); } catch { /* expected */ }
    setRestarting(false);
    setReconnecting(true);
    reconnectDead.current = Date.now() + RECONNECT_TIMEOUT;
    pollHealth();
  };

  useEffect(() => () => { if (reconnectTimer.current) clearInterval(reconnectTimer.current); }, []);

  // ── Render ───────────────────────────────────────────────────────────────────

  const activeCatSettings = settings[activeCategory] ?? [];
  const activeMeta = categories.find(c => c.category === activeCategory);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">

      {/* ── Page header ── */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-purple-500" /> Application Settings
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            All settings are persisted in the database.
            <span className="text-orange-400 font-semibold ml-1">RESTART</span> settings
            require a server restart to take effect.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="p-2 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition cursor-pointer"
            title="Reload settings"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => { setNeedsRestart(true); handleRestart(); }}
            disabled={restarting || reconnecting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-slate-700
              hover:border-amber-700 hover:bg-amber-950/20 hover:text-amber-300 text-slate-400
              disabled:opacity-40 transition cursor-pointer"
            title="Restart the server"
          >
            <Power className="w-3.5 h-3.5" />
            {reconnecting ? 'Restarting…' : 'Restart Server'}
          </button>
        </div>
      </div>

      {/* ── Status banners ── */}
      <div className="px-5 flex flex-col gap-2 shrink-0">
        {error && (
          <div className="mt-3 p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 text-rose-400 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
          </div>
        )}
        {needsRestart && !reconnecting && !restartDone && (
          <div className="mt-3 flex items-center gap-3 px-4 py-3 rounded-xl border border-amber-700/50 bg-amber-950/20">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-300">Restart required</p>
              <p className="text-xs text-amber-500/80 mt-0.5">
                Changes to core settings (database, AI, logging) require a server restart.
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button onClick={() => setNeedsRestart(false)}
                className="px-3 py-1.5 text-xs rounded-lg border border-slate-700 text-slate-400 hover:text-white transition cursor-pointer">
                Dismiss
              </button>
              <button onClick={handleRestart} disabled={restarting}
                className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-60 text-white transition cursor-pointer">
                {restarting
                  ? <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Restarting…</>
                  : <><Power className="w-3.5 h-3.5" /> Restart Server</>}
              </button>
            </div>
          </div>
        )}
        {reconnecting && (
          <div className="mt-3 flex items-center gap-3 px-4 py-3 rounded-xl border border-blue-700/50 bg-blue-950/20">
            <WifiOff className="w-5 h-5 text-blue-400 shrink-0 animate-pulse" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-blue-300">Server is restarting…</p>
              <p className="text-xs text-blue-500/80 mt-0.5">Polling /health — usually takes 3–6 seconds.</p>
            </div>
            <RefreshCw className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
          </div>
        )}
        {reconnectFailed && (
          <div className="mt-3 flex items-center gap-3 px-4 py-3 rounded-xl border border-rose-700/50 bg-rose-950/20">
            <WifiOff className="w-5 h-5 text-rose-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-rose-300">Could not reconnect</p>
              <p className="text-xs text-rose-500/80 mt-0.5">Server did not respond within 30 s. Check the terminal.</p>
            </div>
            <button onClick={() => { setReconnectFailed(false); setNeedsRestart(true); }}
              className="px-3 py-1.5 text-xs rounded-lg border border-rose-700 text-rose-400 hover:text-white transition cursor-pointer shrink-0">
              Try again
            </button>
          </div>
        )}
        {restartDone && (
          <div className="mt-3 flex items-center gap-3 px-4 py-3 rounded-xl border border-emerald-700/50 bg-emerald-950/20">
            <Wifi className="w-5 h-5 text-emerald-400 shrink-0" />
            <p className="text-sm font-semibold text-emerald-300 flex-1">Server restarted — all settings are now active.</p>
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          </div>
        )}
      </div>

      {/* ── Body: sidebar tabs + setting rows ── */}
      <div className="flex flex-1 overflow-hidden mt-4 px-5 pb-5 gap-4">

        {/* Category sidebar */}
        <nav className="w-44 shrink-0 flex flex-col gap-1">
          {categories.map(cat => (
            <button
              key={cat.category}
              onClick={() => setActiveCat(cat.category)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold text-left transition cursor-pointer ${
                activeCategory === cat.category
                  ? 'bg-purple-600/20 border border-purple-500/40 text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
              }`}
            >
              <span>{CATEGORY_ICONS[cat.category] ?? '⚙️'}</span>
              <span className="flex-1 truncate">{cat.label}</span>
              {cat.has_restart_required && (
                <Power className="w-2.5 h-2.5 text-orange-400 shrink-0" />
              )}
            </button>
          ))}
        </nav>

        {/* Settings area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Category header */}
          {activeMeta && (
            <div className="flex items-center justify-between mb-3 shrink-0">
              <div>
                <h3 className="text-sm font-bold text-white">
                  {CATEGORY_ICONS[activeMeta.category] ?? ''} {activeMeta.label}
                </h3>
                <p className="text-[10px] text-slate-500 mt-0.5">{activeMeta.count} settings</p>
              </div>
              <button
                onClick={handleReset}
                disabled={resetting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] rounded-lg border border-slate-700
                  hover:border-rose-700/60 hover:text-rose-400 text-slate-500 transition cursor-pointer disabled:opacity-40"
                title={`Reset all ${activeMeta.label} settings to defaults`}
              >
                <RotateCcw className={`w-3 h-3 ${resetting ? 'animate-spin' : ''}`} />
                Reset to defaults
              </button>
            </div>
          )}

          {/* Rows */}
          <div className="flex-1 overflow-y-auto rounded-xl border border-slate-800/80 bg-[#121620]/30 divide-y divide-slate-800/50">
            {loading ? (
              <div className="flex items-center justify-center py-12 text-slate-500">
                <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading…
              </div>
            ) : activeCatSettings.length === 0 ? (
              <div className="flex items-center justify-center py-12 text-slate-600 text-sm">
                No settings in this category.
              </div>
            ) : activeCatSettings.map(s => {
              const k = sk(s);
              const currentVal = edits[k] ?? s.value;
              const isDirty = edits[k] !== undefined && edits[k] !== s.value;
              const needsRst = RESTART_REQUIRED.has(k);
              const isBoolean = s.value_type === 'boolean';

              return (
                <div key={k} className={`flex items-center gap-4 px-4 py-3 ${isDirty ? 'bg-purple-950/10' : ''}`}>

                  {/* Label col */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs font-mono font-semibold text-slate-300">{s.key}</span>
                      {s.is_secret && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950/30 border border-amber-900/40 text-amber-500">
                          SECRET
                        </span>
                      )}
                      {needsRst && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-950/30 border border-orange-800/40 text-orange-400 flex items-center gap-0.5">
                          <Power className="w-2 h-2" /> RESTART
                        </span>
                      )}
                      <span className="text-[9px] px-1 py-0.5 rounded bg-slate-800/60 text-slate-500 font-mono">
                        {s.value_type}
                      </span>
                    </div>
                    {s.description && (
                      <p className="text-[10px] text-slate-500 mt-0.5 truncate">{s.description}</p>
                    )}
                  </div>

                  {/* Input col */}
                  <div className={`flex items-center gap-2 shrink-0 ${isBoolean ? 'w-auto' : 'w-64'}`}>
                    <SettingInput
                      s={s}
                      value={currentVal}
                      revealed={!!showSecret[k]}
                      onChange={v => handleChange(s, v)}
                      onToggleReveal={() => setShowSecret(p => ({ ...p, [k]: !p[k] }))}
                    />
                    {/* Save button — hidden for booleans (auto-save via toggle) */}
                    {isBoolean ? (
                      isDirty && (
                        <button onClick={() => handleSave(s)}
                          className="p-1.5 rounded-lg border border-purple-500/60 bg-purple-600/20 text-purple-400 hover:bg-purple-600/40 transition cursor-pointer">
                          <Save className="w-3.5 h-3.5" />
                        </button>
                      )
                    ) : (
                      <button
                        onClick={() => handleSave(s)}
                        disabled={!isDirty || saving[k]}
                        title={isDirty ? (needsRst ? 'Save (restart required after)' : 'Save') : 'No changes'}
                        className={`p-1.5 rounded-lg border transition cursor-pointer ${
                          saved[k]
                            ? 'border-emerald-900/40 bg-emerald-950/20 text-emerald-400'
                            : isDirty
                            ? needsRst
                              ? 'border-orange-600/60 bg-orange-950/20 text-orange-400 hover:bg-orange-950/40'
                              : 'border-purple-500/60 bg-purple-600/20 text-purple-400 hover:bg-purple-600/40'
                            : 'border-slate-800 text-slate-600 opacity-40 cursor-not-allowed'
                        }`}
                      >
                        {saved[k]
                          ? <CheckCircle className="w-3.5 h-3.5" />
                          : saving[k]
                          ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          : <Save className="w-3.5 h-3.5" />}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
