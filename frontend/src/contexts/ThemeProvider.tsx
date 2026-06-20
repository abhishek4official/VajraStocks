import React, { createContext, useContext, useEffect, useState } from 'react';

export type Theme = 'carbon' | 'light' | 'cyberpunk' | 'forest' | 'slate';

interface ThemeContextType {
    theme: Theme;
    setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [theme, setThemeState] = useState<Theme>(() => {
        const saved = localStorage.getItem('vajrastocks-theme') as Theme;
        if (saved && ['carbon', 'light', 'cyberpunk', 'forest', 'slate'].includes(saved)) {
            return saved;
        }
        // Default to carbon (dark mode)
        const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
        return prefersLight ? 'light' : 'carbon';
    });

    const setTheme = (newTheme: Theme) => {
        setThemeState(newTheme);
        localStorage.setItem('vajrastocks-theme', newTheme);
    };

    useEffect(() => {
        const root = window.document.documentElement;
        // Clean existing theme attribute
        root.removeAttribute('data-theme');
        if (theme !== 'carbon') {
            root.setAttribute('data-theme', theme);
        }
    }, [theme]);

    return (
        <ThemeContext.Provider value={{ theme, setTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};
