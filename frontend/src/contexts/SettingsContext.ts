import { createContext, useContext } from 'react';
import type { useSettings } from '../hooks/useSettings';

export type SettingsContextValue = ReturnType<typeof useSettings>;

export const SettingsContext = createContext<SettingsContextValue | null>(null);

/** Consume settings anywhere inside <SettingsProvider>. */
export function useSettingsCtx(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettingsCtx must be used inside <SettingsContext.Provider>');
  return ctx;
}
