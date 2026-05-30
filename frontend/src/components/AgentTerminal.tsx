import React, { useState, useRef, useEffect } from 'react';
import { useStockStore } from '../store/useStockStore';
import { Terminal, Send, Sparkles, Cpu, CheckCircle } from 'lucide-react';

export const AgentTerminal: React.FC = () => {
  const { 
    aiIsLoading, 
    aiEvents, 
    aiReport, 
    aiRecommendation, 
    aiConfidence, 
    runAiWorkflow,
    clearAiConsole 
  } = useStockStore();

  const [inputVal, setInputVal] = useState('');
  const consoleEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll the agent event console as stream events arrive
  useEffect(() => {
    consoleEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [aiEvents]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim() || aiIsLoading) return;
    runAiWorkflow(inputVal);
    setInputVal('');
  };

  const handlePresetClick = (preset: string) => {
    if (aiIsLoading) return;
    runAiWorkflow(preset);
  };

  // Custom premium parser to render markdown into high-fidelity Styled JSX
  const renderMarkdown = (text: string | null) => {
    if (!text) return null;

    const lines = text.split('\n');
    let inTable = false;
    let tableHeaders: string[] = [];
    let tableRows: string[][] = [];

    const parsedElements = lines.map((line, idx) => {
      const trimmed = line.trim();

      // Handle table generation
      if (trimmed.startsWith('|')) {
        inTable = true;
        const cells = trimmed.split('|').map(c => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1);
        
        // Skip separator rows e.g. |:---:|:---:|
        if (trimmed.includes('---')) return null;

        if (tableHeaders.length === 0) {
          tableHeaders = cells;
          return null;
        } else {
          tableRows.push(cells);
          return null;
        }
      }

      // Conclude table if present
      if (inTable && !trimmed.startsWith('|')) {
        inTable = false;
        const headers = [...tableHeaders];
        const rows = [...tableRows];
        tableHeaders = [];
        tableRows = [];
        
        return (
          <div key={`table-${idx}`} className="my-4 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/40">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/60 font-mono font-bold text-slate-400">
                  {headers.map((h, i) => (
                    <th key={i} className="p-2.5 px-4 font-bold">{h.replace(/\*\*/g, '')}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850">
                {rows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-slate-900/30 transition">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="p-2.5 px-4 font-mono font-medium text-white">{cell.replace(/\*\*/g, '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }

      // Section Headers
      if (trimmed.startsWith('# ')) {
        return <h1 key={idx} className="text-lg font-extrabold text-white mt-5 mb-2 border-b border-slate-800 pb-1.5 flex items-center gap-2">{trimmed.slice(2)}</h1>;
      }
      if (trimmed.startsWith('## ')) {
        return <h2 key={idx} className="text-md font-bold text-purple-400 mt-4 mb-2 flex items-center gap-1.5">{trimmed.slice(3)}</h2>;
      }
      if (trimmed.startsWith('### ')) {
        return <h3 key={idx} className="text-sm font-semibold text-indigo-400 mt-3 mb-1.5">{trimmed.slice(4)}</h3>;
      }

      // Bullet Lists
      if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
        const content = trimmed.slice(2);
        return (
          <ul key={idx} className="list-disc list-inside text-xs text-slate-300 ml-3 my-1">
            <li>{parseInlineFormatting(content)}</li>
          </ul>
        );
      }

      // Flat text line
      if (trimmed === '') return <div key={idx} className="h-2" />;
      return <p key={idx} className="text-xs text-slate-350 my-1 leading-relaxed">{parseInlineFormatting(trimmed)}</p>;
    });

    return <div className="space-y-1">{parsedElements}</div>;
  };

  // Helper to parse bold text **like this**
  const parseInlineFormatting = (text: string) => {
    const parts = text.split(/\*\*([^*]+)\*\*/g);
    return parts.map((part, index) => {
      if (index % 2 === 1) {
        return <strong key={index} className="text-white font-extrabold">{part}</strong>;
      }
      return part;
    });
  };

  return (
    <div className="flex-1 flex flex-col xl:flex-row gap-5 p-5 overflow-y-auto max-h-full min-h-0" style={{ marginTop: '150px' }}>
      
      {/* LEFT COLUMN: Terminal and SSE Logs Console */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        
        {/* Header Title */}
        <div className="pb-3 border-b border-slate-850 shrink-0">
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Terminal className="w-5 h-5 text-purple-500" />
            AI Quant Agent Console
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Coordinate our 7 independent analytical agents to analyze, scan, and formulate risk plans.
          </p>
        </div>

        {/* Dynamic Preset Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 shrink-0">
          <button
            onClick={() => handlePresetClick('Analyze RELIANCE')}
            disabled={aiIsLoading}
            className="p-3 text-left rounded-xl border border-slate-800/80 bg-[#121620]/20 hover:bg-[#121620]/50 disabled:opacity-40 disabled:cursor-not-allowed hover:border-purple-550/40 text-xs transition cursor-pointer"
          >
            <div className="font-bold text-white flex items-center gap-1.5 mb-1 text-purple-400">
              <Cpu className="w-3.5 h-3.5" />
              Analyze Ticker Setup
            </div>
            <p className="text-[10px] text-slate-400">Deep structural audit, quantitative scoring, and risk entry plan for RELIANCE.</p>
          </button>

          <button
            onClick={() => handlePresetClick('Identify momentum breakout setups')}
            disabled={aiIsLoading}
            className="p-3 text-left rounded-xl border border-slate-800/80 bg-[#121620]/20 hover:bg-[#121620]/50 disabled:opacity-40 disabled:cursor-not-allowed hover:border-purple-550/40 text-xs transition cursor-pointer"
          >
            <div className="font-bold text-white flex items-center gap-1.5 mb-1 text-indigo-400">
              <Sparkles className="w-3.5 h-3.5" />
              Momentum Breakout Scan
            </div>
            <p className="text-[10px] text-slate-400">Scan database snapshot indices to detect volume and structural breakout anomalies.</p>
          </button>

          <button
            onClick={() => handlePresetClick('Report current market regime')}
            disabled={aiIsLoading}
            className="p-3 text-left rounded-xl border border-slate-800/80 bg-[#121620]/20 hover:bg-[#121620]/50 disabled:opacity-40 disabled:cursor-not-allowed hover:border-purple-550/40 text-xs transition cursor-pointer"
          >
            <div className="font-bold text-white flex items-center gap-1.5 mb-1 text-emerald-400">
              <CheckCircle className="w-3.5 h-3.5" />
              Macro Market Regime
            </div>
            <p className="text-[10px] text-slate-400">Assess market indices trend boundaries, flat averages, and volatility bands.</p>
          </button>
        </div>

        {/* Live SSE Logging terminal */}
        <div className="flex-1 bg-[#0c0f17] border border-slate-850 rounded-xl p-4 flex flex-col font-mono text-xs overflow-hidden min-h-[220px]">
          <div className="flex items-center justify-between pb-2 border-b border-slate-850 mb-3 shrink-0 text-slate-400">
            <span className="flex items-center gap-1.5 text-[10px]">
              <span className={`w-2 h-2 rounded-full ${aiIsLoading ? 'bg-purple-500 animate-ping' : 'bg-slate-600'}`} />
              Agent Workflows Stream Logs
            </span>
            <button 
              onClick={clearAiConsole} 
              className="text-[10px] text-slate-500 hover:text-white cursor-pointer transition"
            >
              Clear Logs
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1 select-none">
            {aiEvents.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-650 text-center gap-2 font-sans py-12">
                <Terminal className="w-8 h-8 text-slate-700" />
                <p>Interactive Agent Console Idle.</p>
                <p className="text-[10px] text-slate-500 max-w-[250px]">Choose a preset or type a natural language request below to start.</p>
              </div>
            ) : (
              aiEvents.map((evt, idx) => {
                const isError = evt.status.startsWith('Error') || evt.status.startsWith('Connection');
                return (
                  <div key={idx} className={`p-2.5 rounded-lg border bg-[#121620]/30 transition ${
                    isError 
                      ? 'border-rose-950/40 text-rose-450' 
                      : evt.agent 
                      ? 'border-slate-850 text-slate-300' 
                      : 'border-purple-950/40 text-purple-300'
                  }`}>
                    {evt.agent && (
                      <div className="font-bold text-white flex items-center gap-1 text-[10px] mb-1">
                        <Cpu className="w-3 h-3 text-purple-400" />
                        [{evt.agent.toUpperCase().replace(/_/g, ' ')}]
                      </div>
                    )}
                    <div className="leading-relaxed text-[11px] font-medium whitespace-pre-wrap">{evt.status}</div>
                    
                    {evt.data?.sql_query && (
                      <pre className="mt-2 p-2 rounded bg-slate-950 border border-slate-900 text-emerald-400 overflow-x-auto text-[10px] leading-tight select-all">
                        {evt.data.sql_query}
                      </pre>
                    )}
                  </div>
                );
              })
            )}
            <div ref={consoleEndRef} />
          </div>
        </div>

        {/* Input Bar */}
        <form onSubmit={handleSubmit} className="flex gap-2 shrink-0">
          <input
            type="text"
            disabled={aiIsLoading}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder={aiIsLoading ? "Workflow streaming..." : "Ask AI Agents (e.g. 'Analyze TCS' or 'Find opportunities')..."}
            className="flex-1 px-4 py-2.5 text-xs rounded-xl bg-[#0c0f17] border border-slate-800 text-white focus:outline-none focus:border-purple-500 disabled:opacity-40 disabled:cursor-not-allowed transition"
          />
          <button
            type="submit"
            disabled={!inputVal.trim() || aiIsLoading}
            className="px-4 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-900 disabled:opacity-45 disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer shadow-lg shadow-purple-900/20"
          >
            <Send className="w-3.5 h-3.5" />
            Analyze
          </button>
        </form>
      </div>

      {/* RIGHT COLUMN: Quantitative Investment Report Viewer */}
      <div className="flex-1 flex flex-col gap-4 min-w-0 bg-[#0c0f17] border border-slate-850 rounded-2xl p-5 overflow-hidden">
        
        {/* Recommendation Header Pane */}
        <div className="shrink-0 flex items-center justify-between pb-3 border-b border-slate-850">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Quant Investment Report</h3>
            <div className="text-sm font-bold text-white tracking-tight mt-0.5">Synthesis Review</div>
          </div>

          {aiReport && (
            <div className="flex items-center gap-3">
              <div className="flex flex-col items-end">
                <span className="text-[10px] text-slate-500">Rec</span>
                <span className={`text-xs font-extrabold px-2 py-0.5 rounded-md border font-sans ${
                  aiRecommendation === 'BULLISH'
                    ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30'
                    : aiRecommendation === 'BEARISH'
                    ? 'text-rose-400 bg-rose-950/20 border-rose-900/30'
                    : 'text-amber-400 bg-amber-950/20 border-amber-900/30'
                }`}>
                  {aiRecommendation}
                </span>
              </div>

              <div className="flex flex-col items-end">
                <span className="text-[10px] text-slate-500">Confidence</span>
                <span className={`text-xs font-extrabold px-2 py-0.5 rounded-md border font-sans ${
                  aiConfidence === 'HIGH'
                    ? 'text-purple-400 bg-purple-950/20 border-purple-900/30'
                    : aiConfidence === 'MEDIUM'
                    ? 'text-indigo-400 bg-indigo-950/20 border-indigo-900/30'
                    : 'text-slate-400 bg-slate-900/50 border-slate-800'
                }`}>
                  {aiConfidence}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Investment Report Contents */}
        <div className="flex-1 overflow-y-auto pr-1">
          {aiReport ? (
            <div className="prose prose-invert max-w-none text-slate-300 font-sans leading-relaxed select-text selection:bg-purple-950">
              {renderMarkdown(aiReport)}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-650 text-center gap-3 py-16">
              <Sparkles className="w-12 h-12 text-slate-800 animate-pulse" />
              <div className="space-y-1">
                <p className="font-semibold text-slate-600">Unified Investment Report Panel</p>
                <p className="text-[11px] text-slate-500 max-w-[280px]">Run a multi-agent workflow to synthesize technical data streams and build tactical trade entry maps.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
