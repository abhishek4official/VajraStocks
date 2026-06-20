import React, { useState, useRef, useEffect } from 'react';
import { useTheme, type Theme } from '../contexts/ThemeProvider';
import { Moon, Sun, Zap, Leaf, Snowflake, ChevronDown } from 'lucide-react';

export const ThemeToggle: React.FC = () => {
    const { theme, setTheme } = useTheme();
    const [open, setOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const themes: { id: Theme; label: string; indicatorColor: string; Icon: React.ComponentType<{ className?: string }> }[] = [
        {
            id: 'carbon',
            label: 'Carbon Midnight',
            indicatorColor: 'bg-[#a855f7]',
            Icon: Moon
        },
        {
            id: 'light',
            label: 'Aether Light',
            indicatorColor: 'bg-[#4f46e5]',
            Icon: Sun
        },
        {
            id: 'cyberpunk',
            label: 'Cyberpunk Neon',
            indicatorColor: 'bg-[#39ff14]',
            Icon: Zap
        },
        {
            id: 'forest',
            label: 'Emerald Forest',
            indicatorColor: 'bg-[#10b981]',
            Icon: Leaf
        },
        {
            id: 'slate',
            label: 'Nordic Slate',
            indicatorColor: 'bg-[#38bdf8]',
            Icon: Snowflake
        }
    ];

    const currentTheme = themes.find(t => t.id === theme) || themes[0];
    const CurrentIcon = currentTheme.Icon;

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                onClick={() => setOpen(!open)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800 bg-bg-surface/50 text-slate-400 hover:text-slate-200 hover:border-purple-500/40 hover:bg-bg-surface transition-all select-none cursor-pointer duration-200"
                aria-label="Toggle theme selection"
            >
                <CurrentIcon className="w-3.5 h-3.5 shrink-0" />
                <span className="hidden lg:inline text-xs font-semibold uppercase tracking-wider">{currentTheme.label}</span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${open ? 'rotate-185' : ''}`} />
            </button>

            {open && (
                <div className="absolute right-0 mt-2 w-48 rounded-xl border border-slate-800 bg-bg-surface/95 backdrop-blur-lg p-1.5 shadow-2xl z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                    <div className="px-3 py-1.5 text-[10px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-800/50 mb-1">
                        Select Theme
                    </div>
                    {themes.map(t => {
                        const ItemIcon = t.Icon;
                        return (
                            <button
                                key={t.id}
                                onClick={() => {
                                    setTheme(t.id);
                                    setOpen(false);
                                }}
                                className={`flex w-full items-center gap-3 px-3 py-2 rounded-lg text-left text-xs font-medium transition-all cursor-pointer hover:bg-slate-800/30 ${
                                    theme === t.id ? 'text-purple-400 font-semibold bg-slate-800/40' : 'text-slate-400 hover:text-slate-200'
                                }`}
                            >
                                <ItemIcon className="w-3.5 h-3.5" />
                                <span>{t.label}</span>
                                <span className={`ml-auto w-2 h-2 rounded-full ${t.indicatorColor} shadow-sm`} />
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
