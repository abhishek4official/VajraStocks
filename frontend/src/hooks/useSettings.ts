/**
 * useSettings — app-wide DB-backed settings hook.
 *
 * Features:
 *  • Module-level cache: all consumers share a single fetch, no duplicate requests.
 *  • Typed `get()` accessor: respects value_type (integer / float / boolean / json / string).
 *  • `reload()` busts the cache and re-fetches from the server.
 *  • `invalidateSettingsCache()` lets the SettingsPanel bust the cache after a restart.
 */

import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../lib/apiBase';

const BASE = API_BASE;

export interface Setting {
  id: number;
  category: string;
  key: string;
  value: string;
  value_type: 'string' | 'integer' | 'float' | 'boolean' | 'json';
  description: string | null;
  is_secret: boolean;
}

export type SettingsByCategory = Record<string, Setting[]>;

// ── Module-level cache (shared across all hook instances) ─────────────────────
let _cache: SettingsByCategory | null = null;
let _inflight: Promise<SettingsByCategory> | null = null;

async function _fetchSettings(): Promise<SettingsByCategory> {
  if (_cache) return _cache;
  if (!_inflight) {
    _inflight = fetch(`${BASE}/settings`)
      .then(r => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data: SettingsByCategory) => {
        _cache = data;
        return data;
      })
      .finally(() => { _inflight = null; });
  }
  return _inflight;
}

export function invalidateSettingsCache(): void {
  _cache = null;
}

// ── Hook ──────────────────────────────────────────────────────────────────────
export function useSettings() {
  const [settings, setSettings] = useState<SettingsByCategory>(_cache ?? {});
  const [ready, setReady] = useState(!!_cache);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (_cache) { setSettings(_cache); setReady(true); return; }
    _fetchSettings()
      .then(data => { setSettings(data); setReady(true); })
      .catch(e => setError(String(e)));
  }, []);

  const reload = useCallback(async () => {
    invalidateSettingsCache();
    try {
      const data = await _fetchSettings();
      setSettings(data);
      setReady(true);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  /**
   * Typed getter with fallback.
   * @example get('UI', 'sync_poll_interval_ms', 5000)  // → number
   * @example get('SCREENER', 'default_limit', 2500)     // → number
   * @example get('UI', 'screener_auto_run', false)      // → boolean
   */
  const get = useCallback(
    <T = string>(category: string, key: string, fallback: T): T => {
      const setting = settings[category]?.find(s => s.key === key);
      if (!setting || setting.value === '' || setting.value === null) return fallback;
      const raw = setting.value;
      const type = setting.value_type ?? 'string';
      try {
        if (type === 'integer') return parseInt(raw, 10)   as unknown as T;
        if (type === 'float')   return parseFloat(raw)     as unknown as T;
        if (type === 'boolean') return (['true', '1', 'yes'].includes(raw.toLowerCase())) as unknown as T;
        if (type === 'json')    return JSON.parse(raw)     as T;
      } catch { /* fall through */ }
      return raw as unknown as T;
    },
    [settings],
  );

  return { settings, ready, error, get, reload };
}
