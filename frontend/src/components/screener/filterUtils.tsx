import React from 'react';
import type { ColFilters } from './constants';
import { COL_FILTERS_KEY, DEFAULT_COL_FILTERS } from './constants';

// ── Text / numeric client-side matchers ──────────────────────────────────────
export const matchTextFilter = (val: string | null | undefined, filterStr: string): boolean => {
  if (!filterStr.trim()) return true;
  if (!val) return false;
  return val.toLowerCase().includes(filterStr.toLowerCase().trim());
};

export const matchNumericFilter = (val: number | null | undefined, filterStr: string): boolean => {
  if (!filterStr.trim()) return true;
  if (val === null || val === undefined) return false;
  const trimmed = filterStr.trim().toLowerCase();
  const match = trimmed.match(/^([><]=?|=)?\s*([0-9.-]+)\s*(k|m|cr|crore|crores|l|la|lakh|lakhs)?$/);
  if (!match) return String(val).toLowerCase().includes(trimmed);
  const op = match[1] || '>=';
  let num = parseFloat(match[2]);
  if (isNaN(num)) return true;
  const multiplier = match[3];
  if (multiplier === 'k') num *= 1000;
  else if (multiplier === 'm') num *= 1_000_000;
  else if (multiplier === 'l' || multiplier === 'la' || multiplier === 'lakh' || multiplier === 'lakhs') num *= 100_000;
  else if (multiplier === 'cr' || multiplier === 'crore' || multiplier === 'crores') num *= 10_000_000;
  switch (op) {
    case '>':  return val > num;
    case '<':  return val < num;
    case '>=': return val >= num;
    case '<=': return val <= num;
    case '=':  return val === num;
    default:   return val >= num;
  }
};

export function loadColFilters(): ColFilters {
  try {
    const raw = localStorage.getItem(COL_FILTERS_KEY);
    if (raw) return { ...DEFAULT_COL_FILTERS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return { ...DEFAULT_COL_FILTERS };
}

// ── MultiSelectFilter component ───────────────────────────────────────────────
interface MultiSelectFilterProps {
  options: { value: string; label: string; className?: string }[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minWidth?: string;
}

export const MultiSelectFilter: React.FC<MultiSelectFilterProps> = ({
  options,
  value,
  onChange,
  placeholder = 'All',
  minWidth = '80px',
}) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const selectedValues = React.useMemo(() => (value ? value.split(',') : []), [value]);

  const toggleOption = (val: string) => {
    const newSelected = selectedValues.includes(val)
      ? selectedValues.filter(v => v !== val)
      : [...selectedValues, val];
    onChange(newSelected.join(','));
  };

  React.useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const displayLabel = React.useMemo(() => {
    if (selectedValues.length === 0) return placeholder;
    if (selectedValues.length === options.length) return 'All';
    return selectedValues.map(val => options.find(o => o.value === val)?.label || val).join(', ');
  }, [selectedValues, options, placeholder]);

  return (
    <div className="relative inline-block w-full text-left" style={{ minWidth }} ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-1.5 py-0.5 text-[10px] rounded bg-slate-950 border border-slate-800 text-slate-355 hover:text-text-main hover:border-slate-700 transition cursor-pointer select-none text-left font-mono h-[22px]"
      >
        <span className="truncate mr-1">{displayLabel}</span>
        <span className="text-[8px] text-slate-500">▼</span>
      </button>
      {isOpen && (
        <div className="absolute left-0 mt-1 z-50 min-w-[120px] rounded bg-slate-950 border border-slate-800 shadow-xl py-1 text-[10px] max-h-48 overflow-y-auto">
          {options.map(opt => {
            const isChecked = selectedValues.includes(opt.value);
            return (
              <label
                key={opt.value}
                className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-900 cursor-pointer select-none text-slate-300 hover:text-text-main"
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => toggleOption(opt.value)}
                  className="rounded border-slate-850 bg-slate-900 text-purple-600 focus:ring-0 focus:ring-offset-0 w-3 h-3 cursor-pointer"
                />
                <span className={opt.className}>{opt.label}</span>
              </label>
            );
          })}
          {selectedValues.length > 0 && (
            <div className="border-t border-slate-850/80 mt-1 pt-1 px-2 flex justify-end">
              <button
                type="button"
                onClick={() => onChange('')}
                className="text-[9px] text-purple-400 hover:text-purple-300 font-bold transition"
              >
                Clear
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
