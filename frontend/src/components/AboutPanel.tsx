import React, { useState } from 'react';
import {
  Zap, Database, ShieldCheck, BookOpen, TrendingUp, BarChart2,
  Search, Wallet, Star, RefreshCw, Eye, Target, AlertTriangle,
  ExternalLink, Info, Copy, Check, Sparkles, Cpu, Shield, Heart,
  ChevronDown, ChevronUp
} from 'lucide-react';

const Section: React.FC<{ icon: React.ReactNode; title: string; children: React.ReactNode }> = ({ icon, title, children }) => (
  <div className="rounded-2xl border border-slate-800/80 bg-[#121620]/50 p-6 shadow-lg backdrop-blur-sm shrink-0">
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
  <div className="flex gap-2.5 bg-purple-950/20 border border-purple-500/15 rounded-xl px-4 py-3 text-sm text-slate-300 leading-relaxed shadow-sm">
    <Zap className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
    {children}
  </div>
);

const Warn: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex gap-2.5 bg-amber-950/20 border border-amber-500/20 rounded-xl px-4 py-3 text-sm text-amber-300 leading-relaxed shadow-sm">
    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
    {children}
  </div>
);

type VersionType = 'standard' | 'professional' | 'investor' | 'premium';

export const AboutPanel: React.FC = () => {
  const [activeVersion, setActiveVersion] = useState<VersionType>('standard');
  const [showMarketing, setShowMarketing] = useState(false);
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const marketingAssets = {
    tagline: "Professional-grade swing trading analytics and technical screeners, running locally and privately on your machine—with zero subscription fees.",
    summary: "Vajra Stock is a local-first stock research and decision-support platform designed for swing traders and long-term investors. By utilizing cost-effective End-of-Day (EOD) market data, the platform provides institutional-quality screeners, technical indicators, and multi-timeframe trend scoring. Vajra Stock empowers market participants to identify high-probability setups and manage portfolio risk entirely offline.",
    marketing100: "Vajra Stock is a local-first decision-support platform engineered for swing traders, position traders, and long-term investors in the Indian equity market. By utilizing historical and End-of-Day (EOD) data, the platform computes multi-timeframe indicators, support/resistance confluences, and portfolio risk parameters—all stored securely in a local database with no subscription fees. Vajra Stock removes the noise of intraday price movements, allowing users to run advanced screeners, compare relative strengths, and review portfolio health offline. It is the ultimate tool for strategic market participants who prioritize thorough, objective analysis over high-frequency trading."
  };

  return (
    <div className="flex-1 flex flex-col gap-6 p-6 overflow-y-auto max-h-full bg-[#0a0d14]">

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl border border-purple-500/20 bg-gradient-to-br from-[#161224] via-[#10141e] to-[#090b11] px-8 py-8 shadow-xl shrink-0">
        <div className="absolute -top-20 -right-16 w-72 h-72 bg-purple-600/10 blur-3xl rounded-full pointer-events-none" />
        <div className="absolute -bottom-20 -left-16 w-72 h-72 bg-blue-600/5 blur-3xl rounded-full pointer-events-none" />
        <div className="relative">
          <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
            <div className="flex items-center gap-3.5">
              <span className="p-3 rounded-xl bg-purple-600/15 border border-purple-500/30 text-purple-400 shadow-inner">
                <Zap className="w-7 h-7" />
              </span>
              <div>
                <h1 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-100 to-purple-300 tracking-tight leading-normal py-0.5">
                  Vajra Stock
                </h1>
                <p className="text-xs text-purple-400 font-bold uppercase tracking-widest mt-0.5">
                  NSE Quantitative Research &amp; Decision-Support — v1.5.0
                </p>
              </div>
            </div>
            <a
              href="https://abhishek4official.github.io/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs text-slate-400 hover:text-purple-300 transition duration-200 bg-slate-900/60 hover:bg-slate-900 border border-slate-700/50 hover:border-purple-500/30 rounded-xl px-3.5 py-2 shadow-sm shrink-0"
            >
              <span className="w-6 h-6 rounded-full bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-[10px] font-bold text-purple-300 shrink-0">AK</span>
              <span>Developed by <span className="font-semibold text-slate-200">Abhishek Kumar</span> <span className="text-[10px] text-slate-500 font-mono select-all hover:text-purple-400 transition ml-1">(abhishek4official.github.io)</span></span>
              <ExternalLink className="w-3.5 h-3.5 opacity-60 shrink-0" />
            </a>
          </div>
          <p className="text-slate-300 text-sm leading-relaxed max-w-2xl">
            A secure, local-first stock research terminal built for Indian equity markets. 
            By building a high-speed historical database on your own hardware, Vajra Stock calculates 
            multi-timeframe signals, filters potential breakouts, and evaluates portfolio risk structures 
            privately and subscription-free.
          </p>
        </div>
      </div>

      {/* ── Interactive Version Switcher ────────────────────────────────────── */}
      <div className="flex flex-col gap-4 p-5 rounded-2xl border border-slate-800/80 bg-[#121620]/30 shadow-md shrink-0">
        <div className="flex items-center justify-between flex-wrap gap-2 pb-2">
          <div>
            <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-400" />
              Explore Platform Positioning &amp; Perspectives
            </h2>
            <p className="text-xs text-slate-400">Toggle different copy versions customized for various audience profiles.</p>
          </div>
          <div className="flex bg-slate-900/80 border border-slate-800/80 rounded-xl p-1 shrink-0">
            {(['standard', 'professional', 'investor', 'premium'] as VersionType[]).map((v) => (
              <button
                key={v}
                onClick={() => setActiveVersion(v)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-200 ${
                  activeVersion === v
                    ? 'bg-purple-600/25 text-purple-300 border border-purple-500/30 shadow'
                    : 'text-slate-400 hover:text-slate-200 border border-transparent'
                }`}
              >
                {v === 'investor' ? 'Investor-Friendly' : v}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-[140px] flex flex-col justify-center rounded-xl bg-slate-950/45 border border-slate-900 p-5">
          {activeVersion === 'standard' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-purple-300 font-bold text-sm">
                <BookOpen className="w-4 h-4" />
                <span>Standard (Default Portfolio &amp; Swing Analysis)</span>
              </div>
              <h3 className="text-base font-bold text-white">The Local-First Revolution in Stock Analytics</h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                Vajra Stock is a desktop-class research and decision-support workstation built for Indian equity investors. 
                Unlike cloud-based tools that charge heavy monthly subscriptions, Vajra Stock runs entirely on your own computer. 
                It downloads EOD data, builds a local historical database, and calculates advanced technical and quantitative signals offline.
              </p>
              <p className="text-sm text-slate-300 leading-relaxed">
                The platform is specifically optimized for holding periods of <span className="font-semibold text-purple-400">several days to several months or years</span>. 
                By focusing on End-of-Day (EOD) data, Vajra Stock helps you look past daily market noise, identify solid multi-timeframe trends, 
                screen the entire NSE universe for high-probability setups, and audit your portfolio's risk profile from a single dashboard.
              </p>
            </div>
          )}

          {activeVersion === 'professional' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-blue-400 font-bold text-sm">
                <Cpu className="w-4 h-4" />
                <span>Professional (Quantitative &amp; Institutional)</span>
              </div>
              <h3 className="text-base font-bold text-white">Quantitative Position Management &amp; Trend Confluence</h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                Vajra Stock functions as a local quantitative analytics node. It is designed to perform systematic trend identification, 
                multi-timeframe relative strength screening, and regime-based risk allocation. The system operates on a historical EOD schema, 
                utilizing SQLite or local SQL Server instances to process daily candles, Heikin-Ashi trends, Renko brick distributions, 
                and Three Line Break reversals.
              </p>
              <p className="text-sm text-slate-300 leading-relaxed">
                By utilizing EOD price feeds, the platform enforces <span className="font-semibold text-blue-400">data-latency separation</span>—preventing 
                the psychological friction, noise traps, and emotional execution mistakes associated with real-time intraday tickers. 
                It is engineered for position traders managing holding periods across weeks and months, focusing on structural market trends, 
                Multi-Timeframe (MTF) bias confluences (Daily + Weekly alignment), and mathematical support/resistance clusters.
              </p>
            </div>
          )}

          {activeVersion === 'investor' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                <Heart className="w-4 h-4" />
                <span>Investor-Friendly (Simplified &amp; Strategic)</span>
              </div>
              <h3 className="text-base font-bold text-white">Low-Stress Investing: Focus on the Big Picture</h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                Vajra Stock helps you make smart, calculated decisions in the stock market without the stress of watching live, fluctuating charts. 
                We believe that successful trading and wealth generation is about finding strong, established trends rather than reacting to 
                second-by-second price movements.
              </p>
              <p className="text-sm text-slate-300 leading-relaxed">
                The platform uses stock data that updates at the end of each trading day. This means you can do your research in the evening 
                or on weekends, completely free of market-hour panic. Whether you hold stocks for a few days, weeks, or years, Vajra Stock 
                translates complex mathematical indicators into simple visual cues: <span className="font-semibold text-emerald-400">Bias Chips</span> to 
                show direction, <span className="font-semibold text-emerald-400">Multi-Timeframe Checks</span> to confirm macro trends, and a 
                <span className="font-semibold text-emerald-400">Portfolio Heat Gauge</span> to ensure you aren't taking on too much risk.
              </p>
            </div>
          )}

          {activeVersion === 'premium' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-purple-400 font-bold text-sm">
                <Shield className="w-4 h-4" />
                <span>Premium Product (Strategic Fintech Copy)</span>
              </div>
              <h3 className="text-base font-bold text-white">Uncompromising Performance. Absolute Privacy. Zero Subscriptions.</h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                Vajra Stock represents a new standard in sovereign investment tools. Named after the legendary <span className="italic text-purple-300 font-semibold">Vajra</span>—the 
                indestructible weapon of thunder and clarity—this platform is engineered for investors who demand institutional-grade tools 
                without recurring software costs, advertisement tracking, or privacy compromises.
              </p>
              <p className="text-sm text-slate-300 leading-relaxed">
                By running entirely on your local hardware and utilizing a private local database, Vajra Stock ensures your watchlists, 
                portfolio size, and proprietary trading strategies never leave your machine. Combined with local AI intelligence 
                (powered by your own hardware via Ollama), Vajra Stock provides deep, automated trade planning, relative strength matrices, 
                and risk scoring. It is a premium workstation crafted for those who view trading as a disciplined craft.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Two-column grid ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 shrink-0">

        {/* ── How to use — Trader's Guide ─────────────────────────────────── */}
        <div className="xl:col-span-2">
          <Section icon={<BookOpen className="w-4 h-4" />} title="Trader's Guide — Operations &amp; Workflows">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

              {/* Getting started */}
              <div className="space-y-4">
                <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">First-Time Setup &amp; Initialization</p>
                <div className="space-y-4">
                  <Step n={1} title="Define Local Data Directory">
                    Launch the Vajra Stock server. On first execution, the system will prompt you to set a local
                    <span className="text-slate-200 font-semibold"> data directory</span>—this folder holds your historical SQLite database files locally.
                  </Step>
                  <Step n={2} title="Populate Historical Database (Sync)">
                    Navigate to the <span className="text-purple-300 font-semibold">Sync Centre</span> (gear icon). Trigger a
                    <span className="font-semibold text-slate-200"> Full Sync</span> to pull historical daily candlesticks for all registered NSE symbols (~2,300 stocks) from Yahoo Finance.
                  </Step>
                  <Step n={3} title="Compute Mathematical Indicators">
                    Once the sync completes, run <span className="font-semibold text-slate-200">Recalculate All</span>. The local engine will compute RSI, MACD, CMF, Bollinger Bands, Heikin-Ashi candles, and Support/Resistance confluences.
                  </Step>
                  <Step n={4} title="Import Portfolio Balances">
                    In the <span className="text-purple-300 font-semibold">Portfolio</span> tab, upload your Holdings CSV exported from your broker (e.g., Zerodha Console). Vajra Stock will instantly map indicators and trend biases to your current holdings.
                  </Step>
                </div>
              </div>

              {/* Daily workflow */}
              <div className="space-y-4">
                <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Daily Analytical Routine</p>
                <div className="space-y-4">
                  <Step n={1} title="Execute EOD Sync Post-Close">
                    After market close (3:30 PM IST), initiate an incremental sync from the <span className="font-semibold text-slate-200">Sync Centre</span>. The engine downloads only the latest day's candles, taking less than 2 minutes.
                  </Step>
                  <Step n={2} title="Scan for Trade Setups">
                    Open the <span className="text-purple-300 font-semibold">Screener</span>. Run pre-configured scans like
                    <span className="italic text-slate-300"> RSI Oversold Bounce</span> or <span className="italic text-slate-300">Breakout Watch</span> to identify assets displaying momentum pivots.
                  </Step>
                  <Step n={3} title="Technical Deep-Dive in Explorer">
                    Click any screened symbol to inspect it in the <span className="text-purple-300 font-semibold">Explorer</span>. Alternate between Candlestick, Heikin-Ashi, and Renko charts to review indicator crossovers and structural support/resistance.
                  </Step>
                  <Step n={4} title="Audit Portfolio Risk &amp; Rotation">
                    Open the <span className="text-purple-300 font-semibold">Portfolio</span> dashboard to check total open risk relative to your portfolio size, and examine the <span className="italic text-slate-300">Rotation Candidates</span> to swap weak positions for high-momentum watchlists.
                  </Step>
                </div>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Tip>
                <span><span className="font-semibold text-purple-300">Keyboard Shortcuts:</span> Press <kbd className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-[10px] font-mono">E</kbd> to jump to Explorer, <kbd className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-[10px] font-mono">S</kbd> for Screener, <kbd className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-[10px] font-mono">P</kbd> for Portfolio.</span>
              </Tip>
              <Tip>
                <span><span className="font-semibold text-purple-300">Manual Price Levels:</span> Double-click drawing tools in Explorer to sketch support/resistance lines. These sketches are saved locally per stock code.</span>
              </Tip>
              <Tip>
                <span><span className="font-semibold text-purple-300">Normalised Comparison:</span> Overlay up to 4 symbols in the <span className="text-purple-300 font-semibold">Compare</span> tab to easily see relative strength and momentum leaders.</span>
              </Tip>
            </div>
          </Section>
        </div>

        {/* ── Feature reference ───────────────────────────────────────────── */}
        <Section icon={<Eye className="w-4 h-4" />} title="Workstation Tab Reference">
          <div className="space-y-3">
            {[
              { Icon: BarChart2,  tab: 'Explorer',    desc: 'Deep stock workspace featuring multi-chart structures (Heikin-Ashi, Renko, Line Break), technical overlays, automated support/resistance, and local AI trade planner.' },
              { Icon: Search,     tab: 'Screener',    desc: 'Filter the entire NSE universe using technical confluences. Instantly isolate stocks by trend status, volume triggers, and indicator patterns.' },
              { Icon: Target,     tab: 'Strategy',    desc: 'Multi-factor quantitative models (e.g., Trend Rider, Momentum Burst) that scan the database and output ranked checklists of potential candidates.' },
              { Icon: Wallet,     tab: 'Portfolio',   desc: 'Import brokerage holding files. Analyzes actual holdings for real-time indicator shifts, rotation signals, and open capital risk.' },
              { Icon: Star,       tab: 'Watchlist',   desc: 'A light monitoring board tracking critical trend biases and momentum scores without loading complete charts.' },
              { Icon: TrendingUp, tab: 'Compare',     desc: 'Compares performance by normalising multiple stock paths to a single index point, showing relative momentum.' },
              { Icon: RefreshCw,  tab: 'Sync Centre', desc: 'Control hub for database updates, historical data downloads, database schemas, and mathematical calculations.' },
            ].map(({ Icon, tab, desc }) => (
              <div key={tab} className="flex gap-3 p-3 rounded-xl bg-slate-900/30 border border-slate-800/50 hover:border-slate-800 transition duration-150">
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
        <Section icon={<TrendingUp className="w-4 h-4" />} title="Understanding Algorithmic Outputs">
          <div className="space-y-4 text-sm text-slate-400 leading-relaxed">
            <div className="space-y-1">
              <p className="text-[11px] font-bold uppercase tracking-widest text-purple-400 mb-1">Trend Bias Chips</p>
              <p>
                Displays overall direction (<span className="text-emerald-400 font-semibold">BULLISH</span> / <span className="text-rose-400 font-semibold">BEARISH</span>). 
                The system scores this by combining RSI positioning, MACD crossovers, and the price relationship with the 20, 50, and 200 moving averages.
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-[11px] font-bold uppercase tracking-widest text-purple-400 mb-1">Multi-Timeframe (MTF) Status</p>
              <p>
                Displays whether the weekly macro trend supports the daily setup. A green <span className="text-emerald-400 font-semibold">✓</span> indicates 
                confluence on both Daily and Weekly charts (highest probability). A grey <span className="text-slate-500 font-semibold">✗</span> warns of trend mismatch.
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-[11px] font-bold uppercase tracking-widest text-purple-400 mb-1">Portfolio Risk Heat Gauge</p>
              <p>
                Monitors active exposure. Based on market regimes, the gauge sets a cap on total open risk. 
                If the bar turns <span className="text-rose-400 font-semibold">Red</span>, it indicates you have exceeded your maximum risk allowance; consider pausing new trades.
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-[11px] font-bold uppercase tracking-widest text-purple-400 mb-1">Confluence Support &amp; Resistance (S/R)</p>
              <p>
                Calculates key support and resistance zones. Thicker lines identify key zones where multiple factors align: 
                historical swing pivots, high-volume nodes, and major moving averages.
              </p>
            </div>
          </div>
        </Section>
      </div>

      {/* ── Trust, Transparency, & Data Freshness ───────────────────────────── */}
      <Section icon={<ShieldCheck className="w-4 h-4" />} title="Trust, Transparency, &amp; Data Freshness">
        <div className="space-y-5 text-sm text-slate-300">
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2.5 p-4 rounded-xl bg-slate-900/40 border border-slate-800/80">
              <h4 className="font-bold text-slate-200 flex items-center gap-2">
                <Database className="w-4 h-4 text-purple-400" />
                Data Source &amp; Licensing
              </h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Vajra Stock pulls market data from <span className="text-slate-200">Yahoo Finance</span> using the open-source 
                <code className="bg-slate-800 px-1.5 py-0.5 rounded text-[11px] font-mono text-purple-300 mx-1">yfinance</code> library. 
                All downloaded data is stored locally in your SQLite database. Yahoo Finance data is intended solely for personal, 
                non-commercial research. The platform does not host, resell, or distribute market data to third parties.
              </p>
            </div>

            <div className="space-y-2.5 p-4 rounded-xl bg-slate-900/40 border border-slate-800/80">
              <h4 className="font-bold text-slate-200 flex items-center gap-2">
                <Info className="w-4 h-4 text-purple-400" />
                Data Freshness Policy (Why EOD Data?)
              </h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Professional-grade real-time market data APIs require expensive commercial licensing and specialized streaming servers. 
                To keep Vajra Stock 100% free and subscription-free, we focus on End-of-Day (EOD) and historical data. 
                Data updates once per day after the market close (typically post 3:30 PM IST) and represents the final closing values.
              </p>
            </div>
          </div>

          <div className="space-y-2 p-4 rounded-xl bg-slate-900/40 border border-slate-800/80">
            <h4 className="font-bold text-slate-200">Optimal Use Cases vs. Limitations</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-400 leading-relaxed">
              <div>
                <span className="font-bold text-emerald-400 block mb-1">✓ Designed For:</span>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Swing traders managing trades over holding periods of days to weeks.</li>
                  <li>Long-term investors reviewing portfolio compositions and quarterly charts.</li>
                  <li>Technical analysts screening macro setups and support/resistance confluences.</li>
                  <li>Sovereign traders seeking 100% database privacy and offline analytics.</li>
                </ul>
              </div>
              <div>
                <span className="font-bold text-rose-400 block mb-1">✗ NOT Intended For:</span>
                <ul className="list-disc pl-4 space-y-1">
                  <li>High-frequency day trading, scalping, or live market execution.</li>
                  <li>Real-time price feed monitoring during open market hours.</li>
                  <li>Automated order routing or brokerage execution.</li>
                  <li>Replacing brokerage terminal verification for live prices.</li>
                </ul>
              </div>
            </div>
          </div>

          <Warn>
            <div className="space-y-1">
              <span className="font-bold block">No Financial Advisory:</span>
              <span>
                Vajra Stock is an analytical decision-support software application. It does not provide financial advice, 
                investment recommendations, or buy/sell calls. All signals, calculations, and local AI suggestions are computed 
                algorithmically and are meant purely for educational and research purposes. Stock trading involves significant financial 
                risk. Always verify pricing with your broker and consult a registered financial advisor before trading.
              </span>
            </div>
          </Warn>
        </div>
      </Section>

      {/* ── Collapsible Marketing Summary ───────────────────────────────────── */}
      <div className="rounded-2xl border border-slate-800/80 bg-[#121620]/30 shadow-md overflow-hidden shrink-0">
        <button
          onClick={() => setShowMarketing(!showMarketing)}
          className="w-full flex items-center justify-between p-5 text-sm font-bold text-slate-200 hover:bg-slate-900/30 transition duration-150"
        >
          <span className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
            Vajra Stock Marketing Copy &amp; Summaries (For Branding/Websites)
          </span>
          {showMarketing ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </button>

        {showMarketing && (
          <div className="p-5 border-t border-slate-800/80 bg-[#0c0f17]/50 space-y-4">
            
            {/* Tagline */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">1-Line Tagline</span>
                <button
                  onClick={() => handleCopy(marketingAssets.tagline, 'tagline')}
                  className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-purple-300 transition duration-150"
                >
                  {copiedText === 'tagline' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedText === 'tagline' ? 'Copied!' : 'Copy'}</span>
                </button>
              </div>
              <p className="text-xs text-slate-300 bg-slate-950/50 p-3 rounded-lg border border-slate-900 italic font-medium leading-relaxed">
                "{marketingAssets.tagline}"
              </p>
            </div>

            {/* 3-Line Summary */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">3-Line Summary</span>
                <button
                  onClick={() => handleCopy(marketingAssets.summary, 'summary')}
                  className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-purple-300 transition duration-150"
                >
                  {copiedText === 'summary' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedText === 'summary' ? 'Copied!' : 'Copy'}</span>
                </button>
              </div>
              <p className="text-xs text-slate-300 bg-slate-950/50 p-3 rounded-lg border border-slate-900 leading-relaxed">
                {marketingAssets.summary}
              </p>
            </div>

            {/* 100-Word Version */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">100-Word Marketing Description</span>
                <button
                  onClick={() => handleCopy(marketingAssets.marketing100, 'm100')}
                  className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-purple-300 transition duration-150"
                >
                  {copiedText === 'm100' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedText === 'm100' ? 'Copied!' : 'Copy'}</span>
                </button>
              </div>
              <p className="text-xs text-slate-300 bg-slate-950/50 p-3 rounded-lg border border-slate-900 leading-relaxed">
                {marketingAssets.marketing100}
              </p>
            </div>

          </div>
        )}
      </div>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between text-[11px] text-slate-600 px-1 pb-2 flex-wrap gap-2 shrink-0">
        <span>Vajra Stock v1.5.0 — local-first database, privacy-focused.</span>
        <div className="flex items-center gap-4">
          <a href="https://abhishek4official.github.io/" target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 hover:text-purple-400 transition">
            <ExternalLink className="w-3.5 h-3.5" /> Developed by Abhishek Kumar
          </a>
          <span className="flex items-center gap-1"><Info className="w-3.5 h-3.5" /> Data © Yahoo Finance. Personal use only.</span>
        </div>
      </div>

    </div>
  );
};
