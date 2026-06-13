import React from 'react';
import {
  Zap, Database, ShieldCheck, BookOpen, TrendingUp, BarChart2,
  Search, Wallet, Star, RefreshCw, Eye, Target, AlertTriangle,
  ArrowRight, ExternalLink, Info,
} from 'lucide-react';

const Section: React.FC<{ icon: React.ReactNode; title: string; children: React.ReactNode }> = ({ icon, title, children }) => (
  <div className="rounded-2xl border border-slate-800/80 bg-[#121620]/50 p-6">
    <div className="flex items-center gap-3 mb-4">
      <span className="p-2 rounded-lg bg-purple-600/10 border border-purple-500/20 text-purple-400">{icon}</span>
      <h3 className="text-base font-bold text-white">{title}</h3>
    </div>
    {children}
  </div>
);

const Step: React.FC<{ n: number; title: string; children: React.ReactNode }> = ({ n, title, children }) => (
  <div className="flex gap-4">
    <div className="shrink-0 w-7 h-7 rounded-full bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-xs font-bold text-purple-300 mt-0.5">{n}</div>
    <div>
      <p className="text-sm font-semibold text-slate-200 mb-1">{title}</p>
      <p className="text-sm text-slate-400 leading-relaxed">{children}</p>
    </div>
  </div>
);

const Tip: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex gap-2.5 bg-purple-950/20 border border-purple-500/15 rounded-xl px-4 py-3 text-sm text-slate-300 leading-relaxed">
    <Zap className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
    {children}
  </div>
);

const Warn: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex gap-2.5 bg-amber-950/20 border border-amber-500/20 rounded-xl px-4 py-3 text-sm text-amber-300 leading-relaxed">
    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
    {children}
  </div>
);

export const AboutPanel: React.FC = () => (
  <div className="flex-1 flex flex-col gap-6 p-6 overflow-y-auto max-h-full">

    {/* ── Hero ────────────────────────────────────────────────────────────── */}
    <div className="relative overflow-hidden rounded-2xl border border-purple-500/20 bg-gradient-to-br from-[#15131f] via-[#121620] to-[#0e1016] px-8 py-8">
      <div className="absolute -top-20 -right-16 w-72 h-72 bg-purple-600/10 blur-3xl rounded-full pointer-events-none" />
      <div className="relative">
        <div className="flex items-center gap-3 mb-3">
          <span className="p-2.5 rounded-xl bg-purple-600/15 border border-purple-500/30 text-purple-400">
            <Zap className="w-6 h-6" />
          </span>
          <div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">VajraStocks</h1>
            <p className="text-xs text-purple-400 font-semibold uppercase tracking-widest">NSE Quantitative Analysis Platform — v1.2.0</p>
          </div>
        </div>
        <p className="text-slate-300 text-sm leading-relaxed max-w-2xl">
          A local-first stock analysis tool built for Indian equity traders. It pulls EOD data,
          computes technical indicators and multi-timeframe signals, screens the NSE universe,
          and scores your portfolio — all running entirely on your own machine, with no cloud subscription required.
        </p>
      </div>
    </div>

    {/* ── Two-column grid ─────────────────────────────────────────────────── */}
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

      {/* ── How to use — Trader's Guide ─────────────────────────────────── */}
      <div className="xl:col-span-2">
        <Section icon={<BookOpen className="w-4 h-4" />} title="Trader's Guide — How to use VajraStocks">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

            {/* Getting started */}
            <div className="space-y-4">
              <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">First time setup</p>
              <div className="space-y-4">
                <Step n={1} title="Run the backend once">
                  Open the VajraStocks app or start the backend server. On first run it will ask you to set a
                  <span className="text-slate-200 font-semibold"> data directory</span> — choose any folder on your PC where stock data will be stored.
                </Step>
                <Step n={2} title="Add your universe (Sync)">
                  Go to <span className="text-purple-300 font-semibold">Sync Centre</span> (the gear icon at the top right of the tab bar).
                  Click <span className="font-semibold text-slate-200">Full Sync</span>. This downloads end-of-day prices for all ~2300 NSE stocks from
                  Yahoo Finance. The first sync takes 30–60 minutes depending on your connection.
                </Step>
                <Step n={3} title="Recalculate indicators">
                  After sync completes, click <span className="font-semibold text-slate-200">Recalculate All</span> in the Sync Centre.
                  This runs RSI, MACD, CMF, StochRSI, Bollinger Bands, ATR, moving averages, and Heikin-Ashi across all stocks. Takes ~5–10 minutes.
                </Step>
                <Step n={4} title="Import your portfolio (optional)">
                  Go to <span className="text-purple-300 font-semibold">Portfolio</span>, click <span className="font-semibold text-slate-200">Import CSV</span>,
                  and upload the Holdings CSV from <span className="italic text-slate-300">Zerodha Console → Portfolio → Holdings → Download</span>.
                  Your P&amp;L, open risk, and trade signals are computed instantly.
                </Step>
              </div>
            </div>

            {/* Daily workflow */}
            <div className="space-y-4">
              <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Daily trading workflow</p>
              <div className="space-y-4">
                <Step n={1} title="Run Sync every evening">
                  After market close (3:30 PM IST), trigger a <span className="font-semibold text-slate-200">Full Sync</span> from the Sync Centre.
                  It only downloads the latest day's data — takes 2–5 minutes once your database is already built.
                </Step>
                <Step n={2} title="Screen for opportunities">
                  Open the <span className="text-purple-300 font-semibold">Screener</span> tab. Use pre-built filters like
                  <span className="italic text-slate-300"> RSI Oversold Bounce</span>, <span className="italic text-slate-300">MACD Crossover</span>,
                  or <span className="italic text-slate-300">Breakout Watch</span> — or build your own using the filter controls.
                  Every result shows signal strength, ATR volatility, and weekly momentum at a glance.
                </Step>
                <Step n={3} title="Deep-dive in Explorer">
                  Click any stock in the screener (or search in the left sidebar) to open it in the
                  <span className="text-purple-300 font-semibold"> Explorer</span> tab. Switch between Candlestick, Heikin-Ashi, Renko and Line Break charts.
                  Toggle RSI, MACD, CMF or StochRSI in the indicator panel below the chart. Overlay SMA/EMA/Bollinger Bands to confirm your setup.
                </Step>
                <Step n={4} title="Check your portfolio health">
                  Open <span className="text-purple-300 font-semibold">Portfolio</span> after each sync. The top card shows your total return,
                  open risk as a % of portfolio, and alpha vs NIFTY 50. The <span className="italic text-slate-300">Rotation Candidates</span> section
                  flags weak holdings and suggests stronger alternatives already in your watchlist.
                </Step>
              </div>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Tip>
              <span><span className="font-semibold text-purple-300">Explorer keyboard shortcut:</span> Press <kbd className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-[10px] font-mono">E</kbd> to jump to Explorer, <kbd className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-[10px] font-mono">S</kbd> for Screener, <kbd className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-[10px] font-mono">P</kbd> for Portfolio.</span>
            </Tip>
            <Tip>
              <span><span className="font-semibold text-purple-300">Draw your own levels:</span> In Explorer, enable the pencil Draw Mode to click-draw horizontal price levels on any chart. They persist per symbol.</span>
            </Tip>
            <Tip>
              <span><span className="font-semibold text-purple-300">Compare stocks side-by-side:</span> Use the <span className="text-purple-300 font-semibold">Compare</span> tab to overlay up to 4 stocks normalised to the same starting price.</span>
            </Tip>
          </div>
        </Section>
      </div>

      {/* ── Feature reference ───────────────────────────────────────────── */}
      <Section icon={<Eye className="w-4 h-4" />} title="What each tab does">
        <div className="space-y-3">
          {[
            { Icon: BarChart2,  tab: 'Explorer',    desc: 'Full chart workspace for a single stock — price, volume, indicators, Heikin-Ashi, Renko, Line Break, confluence S/R levels, and an AI trade plan.' },
            { Icon: Search,     tab: 'Screener',    desc: 'Filter the entire NSE universe by technical signal (RSI, MACD, breakout…). Results rank by signal strength and momentum.' },
            { Icon: Target,     tab: 'Strategy',    desc: 'Pre-built multi-factor strategies (Trend Rider, Momentum Burst…). Each strategy scores every stock and gives a ranked shortlist.' },
            { Icon: Wallet,     tab: 'Portfolio',   desc: 'Import your Zerodha holdings. See real P&L, open risk %, portfolio heat, rotation candidates, and trade setups for each holding.' },
            { Icon: Star,       tab: 'Watchlist',   desc: 'Save stocks you are monitoring. Watchlist items show the latest signal and momentum at a glance without full chart loading.' },
            { Icon: TrendingUp, tab: 'Compare',     desc: 'Overlay multiple stocks on a single normalised chart to compare relative strength and momentum side by side.' },
            { Icon: RefreshCw,  tab: 'Sync Centre', desc: 'Schedule or manually trigger EOD data downloads and indicator recalculation. Shows job history and per-symbol sync health.' },
          ].map(({ Icon, tab, desc }) => (
            <div key={tab} className="flex gap-3 p-3 rounded-xl bg-slate-900/30 border border-slate-800/50">
              <Icon className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
              <div>
                <span className="text-xs font-bold text-slate-200">{tab}</span>
                <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── Reading the signals ─────────────────────────────────────────── */}
      <Section icon={<TrendingUp className="w-4 h-4" />} title="Reading the signals — no coding needed">
        <div className="space-y-3 text-sm text-slate-400 leading-relaxed">
          <div className="space-y-2">
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-2">Bias chips (green / red / grey)</p>
            <p>Every stock shows a <span className="text-emerald-400 font-semibold">BULLISH</span> or <span className="text-rose-400 font-semibold">BEARISH</span> bias chip.
              This is computed from RSI position, MACD trend, and price vs key moving averages. <span className="text-emerald-300 font-semibold">VERY_BULLISH</span> means
              all three align bullish on the daily timeframe.</p>
          </div>
          <div className="space-y-2">
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-2">MTF ✓ / ✗ (Multi-Timeframe)</p>
            <p>The <span className="text-slate-200 font-semibold">MTF</span> column in Portfolio and Screener shows whether the weekly chart confirms the daily bias.
              A green ✓ means daily + weekly are both bullish — higher-probability setups. A grey ✗ means a mismatch — trade with smaller size.</p>
          </div>
          <div className="space-y-2">
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-2">Portfolio Heat gauge</p>
            <p>Shows your total open risk as a % of portfolio. The vertical line is your regime-based cap (tighter in bear markets).
              <span className="text-rose-400 font-semibold"> Red bar = above cap</span> — pause new positions until existing ones hit targets or stops.</p>
          </div>
          <div className="space-y-2">
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-2">Confluence S/R levels (Explorer)</p>
            <p>Toggle <span className="text-slate-200 font-semibold">S/R</span> in Explorer overlays to see backend-computed Support and Resistance levels.
              Thicker / brighter lines are higher-strength levels (scored from swing highs, volume nodes, pivots, and moving averages).
              Green lines = support below price, red = resistance above.</p>
          </div>
          <Tip>
            <span>You don't need to know what RSI or ATR mean to use this app. Focus on the <span className="font-semibold text-purple-300">bias chip colour</span>, the <span className="font-semibold text-purple-300">MTF ✓</span>, and whether the <span className="font-semibold text-purple-300">heat gauge is in the green</span>.</span>
          </Tip>
        </div>
      </Section>
    </div>

    {/* ── Data licence ────────────────────────────────────────────────────── */}
    <Section icon={<Database className="w-4 h-4" />} title="Data Source & Licence">
      <div className="space-y-4">
        <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-900/50 border border-slate-700/50">
          <ShieldCheck className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-2 text-sm">
            <p className="font-semibold text-slate-200">Market data is sourced from <span className="text-amber-300">Yahoo Finance</span> via the open-source <code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs font-mono text-amber-300">yfinance</code> library.</p>
            <p className="text-slate-400 leading-relaxed">
              Yahoo Finance data is provided for <span className="font-semibold text-slate-300">personal, non-commercial use only</span>.
              It must not be redistributed, sold, or used in any commercial product without written permission from Yahoo.
              This application stores the data locally on your machine and does not transmit it to any third party.
            </p>
            <p className="text-slate-400 leading-relaxed">
              Prices may be delayed or contain errors. <span className="font-semibold text-slate-300">Always verify prices on your broker platform before placing any order.</span>
              VajraStocks is a research and screening tool — not a trading terminal.
            </p>
          </div>
        </div>
        <Warn>
          VajraStocks is not a registered investment advisor. Nothing shown in this app constitutes investment advice.
          All signals, scores, and trade plans are algorithmic outputs for informational purposes only.
          You are solely responsible for your own trading decisions.
        </Warn>
        <div className="flex flex-wrap gap-3 pt-1">
          <a
            href="https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html"
            target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-purple-300 transition"
          >
            <ExternalLink className="w-3.5 h-3.5" /> Yahoo Terms of Service
          </a>
          <a
            href="https://github.com/ranaroussi/yfinance"
            target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-purple-300 transition"
          >
            <ExternalLink className="w-3.5 h-3.5" /> yfinance on GitHub
          </a>
        </div>
      </div>
    </Section>

    {/* ── Footer ──────────────────────────────────────────────────────────── */}
    <div className="flex items-center justify-between text-[11px] text-slate-600 px-1 pb-2">
      <span>VajraStocks v1.2.0 — local-first, no subscription, no cloud.</span>
      <span className="flex items-center gap-1"><Info className="w-3 h-3" /> Data © Yahoo Finance. For personal use only.</span>
    </div>

  </div>
);
